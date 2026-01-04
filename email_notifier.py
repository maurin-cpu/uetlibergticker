"""
E-Mail-Benachrichtigungsmodul für Flugbarkeits-Alerts
Sendet E-Mails wenn die Konditionen EXCELLENT oder GOOD sind.
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional, Tuple
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Sendet E-Mail-Benachrichtigungen für Flugbarkeits-Alerts."""
    
    def __init__(self):
        """Initialisiert den E-Mail-Notifier mit Konfiguration aus Umgebungsvariablen."""
        self.smtp_server = os.environ.get('EMAIL_SMTP_SERVER')
        self.smtp_port = int(os.environ.get('EMAIL_SMTP_PORT', '587'))
        self.sender = os.environ.get('EMAIL_SENDER')
        self.password = os.environ.get('EMAIL_PASSWORD')
        self.recipient = os.environ.get('EMAIL_RECIPIENT')
        
        self.enabled = all([self.smtp_server, self.sender, self.password, self.recipient])
        
        if not self.enabled:
            logger.warning("E-Mail-Benachrichtigung deaktiviert: Fehlende Konfiguration in .env")
        else:
            logger.info(f"E-Mail-Benachrichtigung aktiviert für {self.recipient}")
    
    def send_alert(self, result: Dict, raise_exception: bool = False, force_send: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Sendet eine E-Mail-Benachrichtigung wenn die Konditionen EXCELLENT oder GOOD sind.
        
        Args:
            result: Evaluierungs-Ergebnis mit conditions, date, rating, etc.
            raise_exception: Wenn True, wird eine Exception geworfen statt False zurückzugeben
            force_send: Wenn True, wird die E-Mail auch gesendet wenn conditions nicht EXCELLENT/GOOD sind
            
        Returns:
            Tuple (success: bool, error_message: Optional[str])
        """
        if not self.enabled:
            error_msg = "E-Mail-Benachrichtigung deaktiviert: Fehlende Konfiguration in .env"
            if raise_exception:
                raise ValueError(error_msg)
            return False, error_msg
        
        conditions = result.get('conditions', '').upper()
        if not force_send and conditions not in ['EXCELLENT', 'GOOD']:
            return False, None
        
        try:
            subject = self._create_subject(result)
            html_body = self._create_html_body(result)
            text_body = self._create_body(result)  # Fallback Plain-Text
            
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender
            msg['To'] = self.recipient
            msg['Subject'] = subject
            
            # Plain-Text Version (Fallback)
            msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
            # HTML Version
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            
            # Verbindung zum SMTP-Server
            try:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10)
            except Exception as e:
                error_msg = f"Verbindung zum SMTP-Server fehlgeschlagen ({self.smtp_server}:{self.smtp_port}): {str(e)}"
                logger.error(error_msg)
                if raise_exception:
                    raise ConnectionError(error_msg)
                return False, error_msg
            
            try:
                server.starttls()
            except Exception as e:
                error_msg = f"TLS-Verbindung fehlgeschlagen: {str(e)}"
                logger.error(error_msg)
                server.quit()
                if raise_exception:
                    raise ConnectionError(error_msg)
                return False, error_msg
            
            try:
                server.login(self.sender, self.password)
            except smtplib.SMTPAuthenticationError as e:
                error_msg = f"Authentifizierung fehlgeschlagen: {str(e)}. Prüfe ob das App-Passwort korrekt ist."
                logger.error(error_msg)
                server.quit()
                if raise_exception:
                    raise ValueError(error_msg)
                return False, error_msg
            except Exception as e:
                error_msg = f"Login-Fehler: {str(e)}"
                logger.error(error_msg)
                server.quit()
                if raise_exception:
                    raise ValueError(error_msg)
                return False, error_msg
            
            try:
                server.send_message(msg)
                server.quit()
            except Exception as e:
                error_msg = f"E-Mail-Versand fehlgeschlagen: {str(e)}"
                logger.error(error_msg)
                server.quit()
                if raise_exception:
                    raise RuntimeError(error_msg)
                return False, error_msg
            
            logger.info(f"E-Mail-Benachrichtigung erfolgreich gesendet für {result.get('date')} ({conditions})")
            return True, None
            
        except Exception as e:
            error_msg = f"Unerwarteter Fehler beim Senden der E-Mail: {str(e)}"
            logger.error(error_msg)
            if raise_exception:
                raise
            return False, error_msg
    
    def _create_subject(self, result: Dict) -> str:
        """Erstellt den E-Mail-Betreff."""
        conditions = result.get('conditions', 'UNKNOWN')
        location = result.get('location', 'Uetliberg')
        date = result.get('date', '')
        
        if date:
            try:
                dt = datetime.strptime(date, "%Y-%m-%d")
                date_str = dt.strftime("%d.%m.%Y")
            except:
                date_str = date
        else:
            date_str = "Unbekannt"
        
        return f"🪂 Flugbarkeits-Alert: {conditions} - {location} {date_str}"
    
    def _create_body(self, result: Dict) -> str:
        """Erstellt den E-Mail-Text."""
        conditions = result.get('conditions', 'UNKNOWN')
        location = result.get('location', 'Uetliberg')
        date = result.get('date', '')
        rating = result.get('rating', 0)
        confidence = result.get('confidence', 0)
        flyable = result.get('flyable', False)
        summary = result.get('summary', 'Keine Zusammenfassung verfügbar')
        details = result.get('details', {})
        recommendation = result.get('recommendation', 'Keine Empfehlung verfügbar')
        
        # Datum formatieren
        if date:
            try:
                dt = datetime.strptime(date, "%Y-%m-%d")
                date_str = dt.strftime("%d.%m.%Y")
                weekday = dt.strftime("%A")
                weekday_de = {
                    'Monday': 'Montag', 'Tuesday': 'Dienstag', 'Wednesday': 'Mittwoch',
                    'Thursday': 'Donnerstag', 'Friday': 'Freitag', 'Saturday': 'Samstag', 'Sunday': 'Sonntag'
                }.get(weekday, weekday)
            except:
                date_str = date
                weekday_de = ""
        else:
            date_str = "Unbekannt"
            weekday_de = ""
        
        # Flugstunden aus config importieren
        try:
            from config import FLIGHT_HOURS_START, FLIGHT_HOURS_END
            flight_hours = f"{FLIGHT_HOURS_START:02d}:00-{FLIGHT_HOURS_END:02d}:00"
        except:
            flight_hours = "9:00-18:00"
        
        # Status-Icon und Text basierend auf Konditionen
        condition_icons = {
            'EXCELLENT': '✅',
            'GOOD': '✅',
            'MODERATE': '⚠️',
            'POOR': '❌',
            'DANGEROUS': '🚫'
        }
        condition_icon = condition_icons.get(conditions, '❓')
        
        flyable_text = "FLUGBAR ✅" if flyable else "NICHT FLUGBAR ❌"
        
        # Rating-Stars
        rating_stars = '⭐' * min(int(rating), 10)
        
        # Confidence-Bar (visuell)
        confidence_bar = '█' * confidence + '░' * (10 - confidence)
        
        body_lines = [
            "╔" + "═" * 68 + "╗",
            "║" + " " * 20 + "🪂 FLUGBARKEITS-ALERT" + " " * 20 + "║",
            "╚" + "═" * 68 + "╝",
            "",
            f"📍 Startplatz: {location}",
            f"📅 Datum: {date_str}" + (f" ({weekday_de})" if weekday_de else ""),
            f"🕐 Flugstunden: {flight_hours}",
            "",
            "━" * 70,
            "",
            f"{condition_icon} Status: {flyable_text}",
            f"📊 Konditionen: {conditions}",
            "",
            f"⭐ Bewertung: {rating_stars} ({rating}/10)",
            f"📈 Konfidenz:  {confidence_bar} ({confidence}/10)",
            "",
            "━" * 70,
            "",
            "📝 ZUSAMMENFASSUNG",
            "─" * 70,
            summary,
            "",
            "━" * 70,
            "",
            "💨 WINDANALYSE",
            "─" * 70,
            details.get('wind', 'Nicht verfügbar'),
            "",
            "━" * 70,
            "",
            "☁️ THERMIK-ANALYSE",
            "─" * 70,
            details.get('thermik', 'Nicht verfügbar'),
            "",
            "━" * 70,
            "",
            "⚠️ RISIKOANALYSE",
            "─" * 70,
            details.get('risks', 'Nicht verfügbar'),
            "",
            "━" * 70,
            "",
            "💡 EMPFEHLUNG",
            "─" * 70,
            recommendation,
            "",
            "━" * 70,
            "",
            f"📧 Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
            "",
            "━" * 70,
        ]
        
        return "\n".join(body_lines)
    
    def _create_html_body(self, result: Dict) -> str:
        """Erstellt den E-Mail-Body im HTML-Format mit allen LLM-Details."""
        conditions = result.get('conditions', 'UNKNOWN')
        location = result.get('location', 'Uetliberg')
        date = result.get('date', '')
        rating = result.get('rating', 0)
        confidence = result.get('confidence', 0)
        flyable = result.get('flyable', False)
        summary = result.get('summary', 'Keine Zusammenfassung verfügbar')
        details = result.get('details', {})
        recommendation = result.get('recommendation', 'Keine Empfehlung verfügbar')
        timestamp = result.get('timestamp', datetime.now().isoformat())
        
        # Datum formatieren
        if date:
            try:
                dt = datetime.strptime(date, "%Y-%m-%d")
                date_str = dt.strftime("%d.%m.%Y")
                weekday = dt.strftime("%A")
                weekday_de = {
                    'Monday': 'Montag', 'Tuesday': 'Dienstag', 'Wednesday': 'Mittwoch',
                    'Thursday': 'Donnerstag', 'Friday': 'Freitag', 'Saturday': 'Samstag', 'Sunday': 'Sonntag'
                }.get(weekday, weekday)
            except:
                date_str = date
                weekday_de = ""
        else:
            date_str = "Unbekannt"
            weekday_de = ""
        
        # Flugstunden aus config importieren
        try:
            from config import FLIGHT_HOURS_START, FLIGHT_HOURS_END
            flight_hours = f"{FLIGHT_HOURS_START:02d}:00-{FLIGHT_HOURS_END:02d}:00"
        except:
            flight_hours = "9:00-18:00"
        
        # Status-Icon und Farbe basierend auf Konditionen
        condition_styles = {
            'EXCELLENT': {'icon': '✅', 'color': '#22c55e', 'bg': '#dcfce7'},
            'GOOD': {'icon': '✅', 'color': '#22c55e', 'bg': '#dcfce7'},
            'MODERATE': {'icon': '⚠️', 'color': '#f59e0b', 'bg': '#fef3c7'},
            'POOR': {'icon': '❌', 'color': '#ef4444', 'bg': '#fee2e2'},
            'DANGEROUS': {'icon': '🚫', 'color': '#dc2626', 'bg': '#fee2e2'}
        }
        style = condition_styles.get(conditions, {'icon': '❓', 'color': '#6b7280', 'bg': '#f3f4f6'})
        
        flyable_text = "FLUGBAR ✅" if flyable else "NICHT FLUGBAR ❌"
        flyable_color = '#22c55e' if flyable else '#ef4444'
        
        # Rating-Stars
        rating_stars = '⭐' * min(int(rating), 10)
        
        # Confidence-Bar (HTML)
        confidence_filled = confidence
        confidence_empty = 10 - confidence
        
        # Formatierung der Details
        wind_analysis = details.get('wind', 'Nicht verfügbar').replace('\n', '<br>')
        thermik_analysis = details.get('thermik', 'Nicht verfügbar').replace('\n', '<br>')
        risks_analysis = details.get('risks', 'Nicht verfügbar').replace('\n', '<br>')
        summary_formatted = summary.replace('\n', '<br>')
        recommendation_formatted = recommendation.replace('\n', '<br>')
        
        html = f"""
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flugbarkeits-Alert: {location}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
        <h1 style="margin: 0; font-size: 28px;">🪂 FLUGBARKEITS-ALERT</h1>
    </div>
    
    <div style="background: white; padding: 30px; border-radius: 0 0 10px 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
        <!-- Header Info -->
        <div style="margin-bottom: 30px;">
            <p style="margin: 5px 0;"><strong>📍 Startplatz:</strong> {location}</p>
            <p style="margin: 5px 0;"><strong>📅 Datum:</strong> {date_str}{' (' + weekday_de + ')' if weekday_de else ''}</p>
            <p style="margin: 5px 0;"><strong>🕐 Flugstunden:</strong> {flight_hours}</p>
        </div>
        
        <hr style="border: none; border-top: 2px solid #e5e7eb; margin: 30px 0;">
        
        <!-- Status -->
        <div style="background: {style['bg']}; padding: 20px; border-radius: 8px; margin-bottom: 30px; border-left: 4px solid {style['color']};">
            <div style="font-size: 24px; margin-bottom: 10px;">
                <span style="color: {style['color']}; font-weight: bold;">{style['icon']} Status: <span style="color: {flyable_color};">{flyable_text}</span></span>
            </div>
            <div style="color: {style['color']}; font-weight: bold; font-size: 18px;">
                📊 Konditionen: {conditions}
            </div>
        </div>
        
        <!-- Rating & Confidence -->
        <div style="display: flex; gap: 30px; margin-bottom: 30px; flex-wrap: wrap;">
            <div style="flex: 1; min-width: 200px;">
                <div style="font-size: 14px; color: #6b7280; margin-bottom: 5px;">⭐ Bewertung</div>
                <div style="font-size: 24px; font-weight: bold;">{rating_stars}</div>
                <div style="font-size: 14px; color: #6b7280;">({rating}/10)</div>
            </div>
            <div style="flex: 1; min-width: 200px;">
                <div style="font-size: 14px; color: #6b7280; margin-bottom: 5px;">📈 Konfidenz</div>
                <div style="font-size: 20px; font-family: monospace; letter-spacing: 2px;">{'█' * confidence_filled}<span style="color: #d1d5db;">{'░' * confidence_empty}</span></div>
                <div style="font-size: 14px; color: #6b7280;">({confidence}/10)</div>
            </div>
        </div>
        
        <hr style="border: none; border-top: 2px solid #e5e7eb; margin: 30px 0;">
        
        <!-- Summary -->
        <div style="margin-bottom: 30px;">
            <h2 style="color: #667eea; margin-bottom: 15px; font-size: 20px;">📝 ZUSAMMENFASSUNG</h2>
            <div style="background: #f9fafb; padding: 15px; border-radius: 6px; border-left: 3px solid #667eea;">
                <p style="margin: 0; line-height: 1.8;">{summary_formatted}</p>
            </div>
        </div>
        
        <!-- Wind Analysis -->
        <div style="margin-bottom: 30px;">
            <h2 style="color: #667eea; margin-bottom: 15px; font-size: 20px;">💨 WINDANALYSE</h2>
            <div style="background: #f9fafb; padding: 15px; border-radius: 6px; border-left: 3px solid #3b82f6;">
                <p style="margin: 0; line-height: 1.8; white-space: pre-wrap;">{wind_analysis}</p>
            </div>
        </div>
        
        <!-- Thermik Analysis -->
        <div style="margin-bottom: 30px;">
            <h2 style="color: #667eea; margin-bottom: 15px; font-size: 20px;">☁️ THERMIK-ANALYSE</h2>
            <div style="background: #f9fafb; padding: 15px; border-radius: 6px; border-left: 3px solid #f59e0b;">
                <p style="margin: 0; line-height: 1.8; white-space: pre-wrap;">{thermik_analysis}</p>
            </div>
        </div>
        
        <!-- Risks Analysis -->
        <div style="margin-bottom: 30px;">
            <h2 style="color: #667eea; margin-bottom: 15px; font-size: 20px;">⚠️ RISIKOANALYSE</h2>
            <div style="background: #f9fafb; padding: 15px; border-radius: 6px; border-left: 3px solid #ef4444;">
                <p style="margin: 0; line-height: 1.8; white-space: pre-wrap;">{risks_analysis}</p>
            </div>
        </div>
        
        <!-- Recommendation -->
        <div style="margin-bottom: 30px;">
            <h2 style="color: #667eea; margin-bottom: 15px; font-size: 20px;">💡 EMPFEHLUNG</h2>
            <div style="background: #f0f9ff; padding: 15px; border-radius: 6px; border-left: 3px solid #0ea5e9;">
                <p style="margin: 0; line-height: 1.8; font-weight: 500;">{recommendation_formatted}</p>
            </div>
        </div>
        
        <hr style="border: none; border-top: 2px solid #e5e7eb; margin: 30px 0;">
        
        <!-- Footer -->
        <div style="text-align: center; color: #6b7280; font-size: 12px; margin-top: 30px;">
            <p style="margin: 5px 0;">📧 Erstellt: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
            <p style="margin: 5px 0;">Uetliberg Ticker - Automatische Wetteranalyse</p>
        </div>
    </div>
</body>
</html>
        """
        return html.strip()
    
    def check_configuration(self) -> Dict[str, any]:
        """
        Überprüft die E-Mail-Konfiguration und gibt detaillierte Informationen zurück.
        
        Returns:
            Dict mit Konfigurationsstatus und Details
        """
        config_status = {
            'enabled': self.enabled,
            'missing_fields': [],
            'configured_fields': {},
            'errors': []
        }
        
        # Prüfe alle Felder
        fields = {
            'EMAIL_SMTP_SERVER': self.smtp_server,
            'EMAIL_SMTP_PORT': self.smtp_port,
            'EMAIL_SENDER': self.sender,
            'EMAIL_PASSWORD': self.password,
            'EMAIL_RECIPIENT': self.recipient
        }
        
        for field_name, field_value in fields.items():
            if field_value:
                # Verstecke Passwort in der Ausgabe
                if 'PASSWORD' in field_name:
                    config_status['configured_fields'][field_name] = '***' if field_value else None
                else:
                    config_status['configured_fields'][field_name] = field_value
            else:
                config_status['missing_fields'].append(field_name)
        
        # Zusätzliche Validierungen
        if self.sender and '@' not in self.sender:
            config_status['errors'].append(f'EMAIL_SENDER scheint keine gültige E-Mail-Adresse zu sein: {self.sender}')
        
        if self.recipient and '@' not in self.recipient:
            config_status['errors'].append(f'EMAIL_RECIPIENT scheint keine gültige E-Mail-Adresse zu sein: {self.recipient}')
        
        if self.smtp_port and self.smtp_port not in [25, 465, 587]:
            config_status['errors'].append(f'EMAIL_SMTP_PORT {self.smtp_port} ist ungewöhnlich. Für Gmail verwende 587 (TLS) oder 465 (SSL).')
        
        return config_status

