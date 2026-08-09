#!/usr/bin/env python3
"""Ueberwacht die Live-Seite: DNS, TLS, HTTP, Inhalt.

Laeuft ohne Abhaengigkeiten, nur Standardbibliothek. Gedacht fuer launchd
(alle 5 Minuten), geht aber auch von Hand:

    python3 tools/watch-site.py              # einmal pruefen
    python3 tools/watch-site.py --verbose    # mit allen Einzelergebnissen
    python3 tools/watch-site.py --install    # launchd-Job einrichten (24/7)
    python3 tools/watch-site.py --uninstall  # launchd-Job entfernen
    python3 tools/watch-site.py --status     # letzter Stand aus der Historie

Alarmiert nur bei Zustandswechsel (OK -> Fehler, Fehler -> OK) und danach
hoechstens einmal pro REMIND_HOURS, damit es nicht alle 5 Minuten piept.
"""
import argparse
import datetime as dt
import json
import os
import re
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Zustand und die von launchd ausgefuehrte Kopie liegen ausserhalb des
# Projektordners: launchd-Prozesse duerfen ~/Desktop nicht lesen (macOS-
# Dateischutz), und der Zustand gehoert ohnehin nicht ins Repo.
HOME_DIR = os.path.expanduser("~/Library/Application Support/auto-tzimagiorgis-watcher")
AGENT_SCRIPT = os.path.join(HOME_DIR, "watch-site.py")
# WATCHER_STATE_DIR nur fuer Probelaeufe setzen, damit ein Test den echten
# Zustand und die echte Historie nicht anfasst.
STATE_DIR = os.environ.get("WATCHER_STATE_DIR") or HOME_DIR
STATE_FILE = os.path.join(STATE_DIR, "state.json")
LOG_FILE = os.path.join(STATE_DIR, "watch.log")
LABEL = "com.dimi.autotzimagiorgis.watcher"
PLIST = os.path.expanduser("~/Library/LaunchAgents/%s.plist" % LABEL)

# WATCHER_DOMAIN / WATCHER_HOST nur fuer Probelaeufe setzen (Feuertest gegen
# eine absichtlich kaputte Adresse). Im Normalbetrieb bleibt es die echte Domain.
DOMAIN = os.environ.get("WATCHER_DOMAIN") or "auto-tzimagiorgis.com"
HOST = os.environ.get("WATCHER_HOST") or ("www." + DOMAIN)
BASE = "https://" + HOST

# GitHub Pages: apex zeigt auf diese vier A-Records, www auf den Pages-Host.
GH_PAGES_IPS = {"185.199.108.153", "185.199.109.153", "185.199.110.153", "185.199.111.153"}
EXPECTED_CNAME = "dimi2404.github.io."

INTERVAL_SECONDS = 300      # launchd-Takt
REMIND_HOURS = 6            # erneut alarmieren, wenn weiter kaputt
TLS_WARN_DAYS = 14          # Zertifikat laeuft bald ab
SLOW_SECONDS = 5.0          # Antwortzeit, ab der wir warnen
TIMEOUT = 20

# Seiten, die immer erreichbar sein muessen, mit einem Textbaustein, der
# beweist, dass wirklich die richtige Seite kam (und nicht eine Fehlerseite).
PAGES = [
    ("/", 'id="cars-grid"'),
    ("/legal.html", "<html"),
    ("/privacy.html", "<html"),
    ("/data/cars.json", '"carGrId"'),
    ("/data/site.json", '"phone"'),
    ("/sitemap.xml", "<urlset"),
    ("/robots.txt", "Sitemap"),
]

UA = "auto-tzimagiorgis-watcher/1.0 (+%s)" % BASE


# ---------------------------------------------------------------- Hilfsmittel

def now():
    return dt.datetime.now(dt.timezone.utc)


def iso(t):
    return t.replace(microsecond=0).isoformat()


def dig(name, rtype):
    """Kurze dig-Abfrage. Leere Liste heisst: keine Antwort.
    None heisst: dig fehlt oder brach ab - das ist kein DNS-Ausfall und darf
    nicht als solcher gemeldet werden."""
    try:
        out = subprocess.run(
            ["dig", "+short", "+time=5", "+tries=2", name, rtype],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return [line.strip() for line in out.splitlines() if line.strip()]


def fetch(path):
    """Holt eine Seite. Gibt (status, sekunden, text, fehler) zurueck."""
    url = BASE + path
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    start = now()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read(400_000).decode("utf-8", "replace")
            secs = (now() - start).total_seconds()
            return resp.getcode(), secs, body, None
    except urllib.error.HTTPError as exc:
        return exc.code, (now() - start).total_seconds(), "", None
    except (urllib.error.URLError, socket.timeout, ssl.SSLError, OSError) as exc:
        return None, (now() - start).total_seconds(), "", str(exc)


# ------------------------------------------------------------------- Pruefung

class Result(object):
    """Ein Einzelbefund. severity: ok | warn | fail"""

    def __init__(self, area, name, severity, detail, hint=""):
        self.area = area
        self.name = name
        self.severity = severity
        self.detail = detail
        self.hint = hint

    def as_dict(self):
        return {"area": self.area, "name": self.name, "severity": self.severity,
                "detail": self.detail, "hint": self.hint}


def check_dns():
    out = []
    www_cname = dig(HOST, "CNAME")
    if www_cname is None:
        return [Result("DNS", "dig", "warn", "dig nicht verfuegbar - DNS ungeprueft",
                       "dnsutils installieren (Linux: sudo apt-get install -y dnsutils).")]
    if not www_cname:
        out.append(Result("DNS", "www CNAME", "fail", "kein CNAME fuer %s" % HOST,
                          "Beim Registrar (Namecheap) CNAME www -> %s eintragen." % EXPECTED_CNAME))
    elif www_cname[0].lower() != EXPECTED_CNAME:
        out.append(Result("DNS", "www CNAME", "fail",
                          "zeigt auf %s statt %s" % (www_cname[0], EXPECTED_CNAME),
                          "Fremder Eintrag - Registrar-Zugang pruefen."))
    else:
        out.append(Result("DNS", "www CNAME", "ok", www_cname[0]))

    # dig gibt bei einer A-Abfrage auf www auch die CNAME-Zeile aus - nur IPs behalten.
    def ips(name):
        return {v for v in (dig(name, "A") or []) if re.match(r"^\d+\.\d+\.\d+\.\d+$", v)}

    www_a = ips(HOST)
    apex_a = ips(DOMAIN)
    for label, got in (("www A", www_a), ("apex A", apex_a)):
        if not got:
            out.append(Result("DNS", label, "fail", "keine A-Records",
                              "DNS-Ausfall oder Domain abgelaufen - Registrar pruefen."))
        elif not got & GH_PAGES_IPS:
            out.append(Result("DNS", label, "fail", "zeigt auf %s" % ", ".join(sorted(got)),
                              "Keine GitHub-Pages-IP. A-Records auf 185.199.108-111.153 setzen."))
        elif got != GH_PAGES_IPS:
            out.append(Result("DNS", label, "warn",
                              "nur %d von 4 IPs: %s" % (len(got & GH_PAGES_IPS), ", ".join(sorted(got))),
                              "Alle vier A-Records eintragen, sonst faellt Ausfallsicherheit weg."))
        else:
            out.append(Result("DNS", label, "ok", "4 GitHub-Pages-IPs"))

    ns = dig(DOMAIN, "NS") or []
    out.append(Result("DNS", "Nameserver", "ok" if ns else "fail",
                      ", ".join(ns) if ns else "keine Nameserver",
                      "" if ns else "Domain moeglicherweise abgelaufen oder gesperrt."))
    return out


def check_tls():
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((HOST, 443), timeout=TIMEOUT) as sock:
            with ctx.wrap_socket(sock, server_hostname=HOST) as tls:
                cert = tls.getpeercert()
    except ssl.SSLCertVerificationError as exc:
        return [Result("TLS", "Zertifikat", "fail", "ungueltig: %s" % exc.verify_message,
                       "GitHub Pages: 'Enforce HTTPS' aus- und wieder einschalten, "
                       "damit Let's Encrypt neu ausstellt.")]
    except (ssl.SSLError, socket.timeout, OSError) as exc:
        return [Result("TLS", "Handshake", "fail", str(exc),
                       "Port 443 nicht erreichbar oder TLS abgebrochen.")]

    expires = dt.datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(
        tzinfo=dt.timezone.utc)
    days = (expires - now()).days
    names = {v for k, v in cert.get("subjectAltName", ()) if k == "DNS"}
    out = []
    if days < 0:
        out.append(Result("TLS", "Ablauf", "fail", "abgelaufen am %s" % iso(expires),
                          "Zertifikat erneuern lassen (GitHub Pages HTTPS neu anstossen)."))
    elif days <= TLS_WARN_DAYS:
        out.append(Result("TLS", "Ablauf", "warn", "laeuft in %d Tagen ab" % days,
                          "Normalerweise erneuert Let's Encrypt automatisch. Beobachten."))
    else:
        out.append(Result("TLS", "Ablauf", "ok", "%d Tage gueltig" % days))
    if names and HOST not in names and not any(n.startswith("*.") for n in names):
        out.append(Result("TLS", "Hostname", "fail", "Zertifikat gilt fuer %s" % ", ".join(sorted(names)),
                          "Custom Domain in den GitHub-Pages-Einstellungen pruefen."))
    return out


def check_pages():
    out = []
    for path, sentinel in PAGES:
        status, secs, body, err = fetch(path)
        if err:
            out.append(Result("HTTP", path, "fail", "keine Antwort (%s)" % err,
                              "Netz, DNS oder GitHub Pages down. status.github.com pruefen."))
            continue
        if status != 200:
            hint = ("Datei fehlt im Repo oder Pfad falsch." if status == 404 else
                    "GitHub Pages liefert Serverfehler - status.github.com pruefen."
                    if status >= 500 else "")
            out.append(Result("HTTP", path, "fail", "HTTP %d" % status, hint))
            continue
        if sentinel not in body:
            out.append(Result("Inhalt", path, "fail",
                              "erwarteter Baustein %r fehlt" % sentinel,
                              "Seite antwortet, aber mit falschem Inhalt. Letzten Deploy pruefen."))
            continue
        sev = "warn" if secs > SLOW_SECONDS else "ok"
        detail = "HTTP 200 in %.2fs" % secs
        out.append(Result("HTTP", path, sev, detail,
                          "Ungewoehnlich langsam." if sev == "warn" else ""))
    return out


def check_inventory():
    """Fahrzeugbestand: JSON lesbar, Anzahl plausibel, Stichprobe erreichbar."""
    out = []
    status, _, body, err = fetch("/data/cars.json")
    if status != 200 or err:
        return [Result("Bestand", "cars.json", "fail", err or "HTTP %s" % status,
                       "Ohne cars.json zeigt die Startseite keine Fahrzeuge.")]
    try:
        cars = json.loads(body)
    except ValueError as exc:
        return [Result("Bestand", "cars.json", "fail", "kaputtes JSON: %s" % exc,
                       "Import neu laufen lassen: python3 tools/import-cargr.py")]
    if not isinstance(cars, list) or not cars:
        return [Result("Bestand", "cars.json", "fail", "leere Liste",
                       "Import hat keine Fahrzeuge geliefert (car.gr 429?).")]
    out.append(Result("Bestand", "Anzahl", "ok", "%d Fahrzeuge" % len(cars)))

    # Eine Detailseite und ein Bild als Stichprobe - rotiert ueber die Laeufe,
    # damit mit der Zeit alles einmal geprueft wird.
    idx = int(now().timestamp() // INTERVAL_SECONDS) % len(cars)
    car = cars[idx]
    car_id = car.get("id") or ""
    status, _, body, err = fetch("/cars/%s.html" % car_id)
    if status == 200 and not err:
        out.append(Result("Bestand", "Detailseite", "ok", "%s.html" % car_id))
    else:
        out.append(Result("Bestand", "Detailseite", "fail",
                          "/cars/%s.html -> %s" % (car_id, err or "HTTP %s" % status),
                          "Seiten neu erzeugen: SITE_URL=%s python3 tools/build_pages.py" % BASE))

    images = car.get("imagesLarge") or car.get("images") or []
    if images:
        img = images[0]
        path = img if img.startswith("/") else "/" + img
        if img.startswith("http"):
            path = re.sub(r"^https?://[^/]+", "", img)
        status, _, _, err = fetch(path)
        if status == 200 and not err:
            out.append(Result("Bestand", "Foto", "ok", path))
        else:
            out.append(Result("Bestand", "Foto", "fail",
                              "%s -> %s" % (path, err or "HTTP %s" % status),
                              "Bilder fehlen im Repo oder wurden nicht gepusht."))
    return out


def run_checks():
    results = []
    results += check_dns()
    # Ohne DNS haben HTTP-Pruefungen keinen Sinn - sie wuerden nur Folgefehler melden.
    if any(r.severity == "fail" for r in results):
        results.append(Result("HTTP", "uebersprungen", "warn",
                              "erst DNS reparieren", ""))
        return results
    results += check_tls()
    results += check_pages()
    if not any(r.severity == "fail" and r.area == "HTTP" for r in results):
        results += check_inventory()
    return results


# ---------------------------------------------------------------- Auswertung

def summarize(results):
    fails = [r for r in results if r.severity == "fail"]
    warns = [r for r in results if r.severity == "warn"]
    status = "DOWN" if fails else ("WARN" if warns else "OK")

    if fails:
        areas = []
        for r in fails:
            if r.area not in areas:
                areas.append(r.area)
        headline = "%s: %s (%d Problem%s)" % (
            HOST, "/".join(areas), len(fails), "" if len(fails) == 1 else "e")
        body = "\n".join("%s %s - %s" % (r.area, r.name, r.detail) for r in fails[:5])
        hints = [r.hint for r in fails if r.hint]
        if hints:
            body += "\n\nNaechster Schritt: " + hints[0]
    elif warns:
        headline = "%s: %d Warnung%s" % (HOST, len(warns), "" if len(warns) == 1 else "en")
        body = "\n".join("%s %s - %s" % (r.area, r.name, r.detail) for r in warns[:5])
    else:
        headline = "%s: alles in Ordnung" % HOST
        body = "%d Pruefungen bestanden" % len(results)
    return status, headline, body


# ---------------------------------------------------------------- Alarmierung

def notify_mac(title, message):
    text = message.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " | ")
    title = title.replace('"', "'")
    script = 'display notification "%s" with title "Website-Watcher" subtitle "%s" sound name "Basso"' % (
        text[:230], title[:100])
    try:
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        pass


def notify_webhook(payload):
    """Optional: WATCHER_WEBHOOK setzen (Slack/Discord/eigener Endpunkt)."""
    url = os.environ.get("WATCHER_WEBHOOK")
    if not url:
        return
    data = json.dumps({"text": payload}).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                headers={"Content-Type": "application/json", "User-Agent": UA})
    try:
        urllib.request.urlopen(req, timeout=15).read()
    except Exception:  # Alarm darf die Pruefung nie kippen
        pass


def write_brain(status, headline, body, results):
    """Notiz fuer Obsidian, damit ein Agent den Verlauf nachlesen kann."""
    vault = os.environ.get("WATCHER_VAULT",
                           os.path.expanduser("~/Documents/Obsidian Vault"))
    if not os.path.isdir(vault):
        return
    folder = os.path.join(vault, "Auto Tzimagiorgis")
    try:
        os.makedirs(folder, exist_ok=True)
        icon = {"OK": "✅", "WARN": "⚠️", "DOWN": "🔴"}[status]
        lines = [
            "---",
            "status: %s" % status,
            "geprueft: %s" % iso(now()),
            "domain: %s" % HOST,
            "tags: [website, monitoring]",
            "---",
            "",
            "# %s Website-Status" % icon,
            "",
            "**%s**" % headline,
            "",
            body,
            "",
            "## Alle Pruefungen",
            "",
            "| Bereich | Pruefung | Ergebnis | Detail |",
            "| --- | --- | --- | --- |",
        ]
        mark = {"ok": "✅", "warn": "⚠️", "fail": "🔴"}
        for r in results:
            lines.append("| %s | %s | %s | %s |" % (
                r.area, r.name, mark[r.severity], r.detail.replace("|", "\\|")))
        lines += ["", "Historie: `%s`" % LOG_FILE, ""]
        with open(os.path.join(folder, "Website-Status.md"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))
    except OSError:
        pass


# --------------------------------------------------------------------- Zustand

def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_state(state):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)


def append_log(status, headline):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write("%s\t%s\t%s\n" % (iso(now()), status, headline))


def should_alert(state, status):
    """Nur bei Wechsel alarmieren, sonst hoechstens alle REMIND_HOURS."""
    previous = state.get("status")
    if previous is None and status == "OK":
        return False, ""  # erster Lauf und alles gut - kein Grund zu piepen
    if previous != status:
        return True, "Wechsel %s -> %s" % (previous or "?", status)
    if status == "OK":
        return False, ""
    last = state.get("last_alert")
    if not last:
        return True, "erste Meldung"
    try:
        then = dt.datetime.fromisoformat(last)
    except ValueError:
        return True, "Zeitstempel unlesbar"
    hours = (now() - then).total_seconds() / 3600
    if hours >= REMIND_HOURS:
        return True, "weiterhin %s seit %.0f h" % (status, hours)
    return False, ""


# ------------------------------------------------------------------- launchd

PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{label}</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>{script}</string>
  </array>
  <key>WorkingDirectory</key><string>{root}</string>
  <key>StartInterval</key><integer>{interval}</integer>
  <key>RunAtLoad</key><true/>
  <key>StandardOutPath</key><string>{stdout}</string>
  <key>StandardErrorPath</key><string>{stderr}</string>
</dict>
</plist>
"""


def install():
    os.makedirs(STATE_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(PLIST), exist_ok=True)
    # Arbeitskopie anlegen. Nach jeder Aenderung am Skript --install erneut
    # aufrufen, sonst laeuft der Dienst weiter mit der alten Fassung.
    if os.path.abspath(__file__) != AGENT_SCRIPT:
        with open(os.path.abspath(__file__), encoding="utf-8") as src:
            code = src.read()
        with open(AGENT_SCRIPT, "w", encoding="utf-8") as dst:
            dst.write(code)
        os.chmod(AGENT_SCRIPT, 0o755)
    with open(PLIST, "w", encoding="utf-8") as fh:
        fh.write(PLIST_TEMPLATE.format(
            label=LABEL, script=AGENT_SCRIPT, root=HOME_DIR,
            interval=INTERVAL_SECONDS,
            stdout=os.path.join(STATE_DIR, "launchd.out"),
            stderr=os.path.join(STATE_DIR, "launchd.err")))
    uid = os.getuid()
    subprocess.run(["launchctl", "bootout", "gui/%d/%s" % (uid, LABEL)],
                   capture_output=True)
    done = subprocess.run(["launchctl", "bootstrap", "gui/%d" % uid, PLIST],
                          capture_output=True, text=True)
    if done.returncode != 0:
        print("launchctl bootstrap fehlgeschlagen: %s" % done.stderr.strip())
        return 1
    print("Watcher laeuft. Takt: alle %d Minuten." % (INTERVAL_SECONDS // 60))
    print("plist: %s" % PLIST)
    print("Log:   %s" % LOG_FILE)
    return 0


def uninstall():
    subprocess.run(["launchctl", "bootout", "gui/%d/%s" % (os.getuid(), LABEL)],
                   capture_output=True)
    if os.path.exists(PLIST):
        os.remove(PLIST)
    print("Watcher entfernt. Historie in %s bleibt erhalten." % STATE_DIR)
    return 0


def show_status():
    state = load_state()
    if not state:
        print("Noch kein Lauf. Einmal 'python3 tools/watch-site.py' starten.")
        return 1
    print("Stand:    %s" % state.get("status"))
    print("Geprueft: %s" % state.get("checked"))
    print("Meldung:  %s" % state.get("headline"))
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, encoding="utf-8") as fh:
            tail = fh.readlines()[-10:]
        print("\nLetzte Laeufe:")
        for line in tail:
            print("  " + line.rstrip())
    return 0


# --------------------------------------------------------------- GitHub Actions

def ci_report(status, headline, body, results):
    """Bericht fuer den Workflow. Markdown nach ci-report.md, Kurzfassung nach
    $GITHUB_OUTPUT, Exitcode 0 bei OK/WARN und 2 bei DOWN."""
    mark = {"ok": "✅", "warn": "⚠️", "fail": "🔴"}
    lines = ["## %s %s" % (mark["ok" if status == "OK" else
                           "warn" if status == "WARN" else "fail"], headline), ""]
    if status != "OK":
        lines += [body, ""]
    lines += ["| Bereich | Pruefung | Ergebnis | Detail |", "| --- | --- | --- | --- |"]
    for r in results:
        lines.append("| %s | %s | %s | %s |" % (
            r.area, r.name, mark[r.severity], r.detail.replace("|", "\\|")))
    hints = [r.hint for r in results if r.hint and r.severity == "fail"]
    if hints:
        lines += ["", "**Naechste Schritte**", ""]
        lines += ["- %s" % h for h in dict.fromkeys(hints)]
    lines += ["", "_Geprueft: %s_" % iso(now())]
    report = "\n".join(lines) + "\n"

    with open("ci-report.md", "w", encoding="utf-8") as fh:
        fh.write(report)

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write("status=%s\n" % status)
            fh.write("headline=%s\n" % headline.replace("\n", " "))

    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(report)

    print(report)
    return 2 if status == "DOWN" else 0


# ----------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="Watcher fuer %s" % BASE)
    ap.add_argument("--install", action="store_true", help="launchd-Job einrichten")
    ap.add_argument("--uninstall", action="store_true", help="launchd-Job entfernen")
    ap.add_argument("--status", action="store_true", help="letzten Stand zeigen")
    ap.add_argument("--verbose", action="store_true", help="alle Einzelergebnisse")
    ap.add_argument("--force-alert", action="store_true", help="Alarm auch ohne Wechsel")
    ap.add_argument("--ci", action="store_true",
                    help="fuer GitHub Actions: kein Zustand, keine Mitteilung, "
                         "Bericht nach stdout, Exitcode als Ergebnis")
    args = ap.parse_args()

    if args.install:
        return install()
    if args.uninstall:
        return uninstall()
    if args.status:
        return show_status()

    results = run_checks()
    status, headline, body = summarize(results)

    if args.ci:
        # In Actions gibt es keinen Desktop und keinen Vault. Die Entdopplung
        # macht dort das GitHub-Issue, nicht die state.json.
        return ci_report(status, headline, body, results)

    state = load_state()
    alert, reason = should_alert(state, status)
    if args.force_alert:
        alert, reason = True, "erzwungen"

    append_log(status, headline)
    write_brain(status, headline, body, results)

    if alert:
        notify_mac(headline, body)
        notify_webhook("%s\n%s" % (headline, body))
        state["last_alert"] = iso(now())

    if status != state.get("status"):
        state["since"] = iso(now())
    state["status"] = status
    state["checked"] = iso(now())
    state["headline"] = headline
    state["results"] = [r.as_dict() for r in results]
    save_state(state)

    mark = {"ok": "ok  ", "warn": "warn", "fail": "FAIL"}
    print("[%s] %s" % (status, headline))
    if args.verbose or status != "OK":
        for r in results:
            print("  %s %-8s %-16s %s" % (mark[r.severity], r.area, r.name, r.detail))
            if r.hint and r.severity != "ok":
                print("       -> %s" % r.hint)
    if alert:
        print("Alarm ausgeloest (%s)." % reason)
    return 0 if status == "OK" else (1 if status == "WARN" else 2)


if __name__ == "__main__":
    sys.exit(main())
