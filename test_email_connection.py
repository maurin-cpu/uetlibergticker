#!/usr/bin/env python3
"""
Test-Skript zum Debuggen der E-Mail-Verbindung
"""

import os
import smtplib
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("E-Mail Konfiguration Test")
print("=" * 60)

smtp_server = os.environ.get('EMAIL_SMTP_SERVER')
smtp_port = int(os.environ.get('EMAIL_SMTP_PORT', '587'))
sender = os.environ.get('EMAIL_SENDER')
password = os.environ.get('EMAIL_PASSWORD', '')
recipient = os.environ.get('EMAIL_RECIPIENT')

print(f"\nSMTP Server: {smtp_server}")
print(f"SMTP Port: {smtp_port}")
print(f"Sender: {sender}")
print(f"Recipient: {recipient}")
print(f"Password Length: {len(password)} Zeichen")
print(f"Password has spaces: {' ' in password}")
print(f"Password (first 4): {password[:4] if password else 'N/A'}***")

if not all([smtp_server, sender, password, recipient]):
    print("\n[FEHLER] Nicht alle Felder sind gesetzt!")
    missing = []
    if not smtp_server:
        missing.append("EMAIL_SMTP_SERVER")
    if not sender:
        missing.append("EMAIL_SENDER")
    if not password:
        missing.append("EMAIL_PASSWORD")
    if not recipient:
        missing.append("EMAIL_RECIPIENT")
    print(f"Fehlende Felder: {', '.join(missing)}")
    exit(1)

print("\n" + "=" * 60)
print("Teste Verbindung...")
print("=" * 60)

try:
    print(f"\n1. Verbinde zu {smtp_server}:{smtp_port}...")
    server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
    print("   [OK] Verbindung erfolgreich")
    
    print("\n2. Starte TLS...")
    server.starttls()
    print("   [OK] TLS erfolgreich")
    
    print("\n3. Versuche Login...")
    print(f"   Username: {sender}")
    print(f"   Password: {'*' * len(password)}")
    server.login(sender, password)
    print("   [OK] Login erfolgreich!")
    
    print("\n4. Verbindung schließen...")
    server.quit()
    print("   [OK] Verbindung geschlossen")
    
    print("\n" + "=" * 60)
    print("[OK] ALLE TESTS ERFOLGREICH!")
    print("=" * 60)
    
except smtplib.SMTPAuthenticationError as e:
    print(f"\n[FEHLER] AUTHENTIFIZIERUNGSFEHLER: {e}")
    print("\nMogliche Ursachen:")
    print("1. App-Passwort ist falsch kopiert (mit Leerzeichen?)")
    print("2. E-Mail-Adresse stimmt nicht uberein")
    print("3. App-Passwort wurde geloscht oder ist abgelaufen")
    print("4. Zwei-Faktor-Authentifizierung nicht aktiviert")
    print("\nLosung:")
    print("- Erstelle ein NEUES App-Passwort in Google")
    print("- Kopiere es komplett ohne Leerzeichen")
    print("- Stelle sicher, dass EMAIL_SENDER genau deine Gmail-Adresse ist")
    print("\nWichtig:")
    print("- Pruefe ob in der .env Datei Anfuhrungszeichen um die Werte sind")
    print("- Pruefe ob das Passwort Leerzeichen enthalt")
    print("- Stelle sicher, dass EMAIL_SENDER genau deine Gmail-Adresse ist")
    
except Exception as e:
    print(f"\n[FEHLER] {e}")
    print(f"Fehlertyp: {type(e).__name__}")
    import traceback
    traceback.print_exc()

