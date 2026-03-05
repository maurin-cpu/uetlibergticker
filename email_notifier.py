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
    
    FIXED_RECIPIENT = "mutschgito@hotmail.com"

    def __init__(self):
        """Initialisiert den E-Mail-Notifier mit Konfiguration aus Umgebungsvariablen."""
        self.smtp_server = os.environ.get('EMAIL_SMTP_SERVER')
        self.smtp_port = int(os.environ.get('EMAIL_SMTP_PORT', '587'))
        self.sender = os.environ.get('EMAIL_SENDER')
        self.password = os.environ.get('EMAIL_PASSWORD')
        self.recipient = os.environ.get('EMAIL_RECIPIENT')
        self.base_url = os.environ.get('APP_BASE_URL', 'https://uetliberg-ticker.vercel.app')

        self.enabled = all([self.smtp_server, self.sender, self.password, self.recipient])

        if not self.enabled:
            logger.warning("E-Mail-Benachrichtigung deaktiviert: Fehlende Konfiguration in .env")
        else:
            logger.info(f"E-Mail-Benachrichtigung aktiviert fuer {self.recipient}")
    
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
    
    def send_multi_day_alert(self, results_list: list, raise_exception: bool = False, force_send: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Sendet EINE konsolidierte E-Mail für ALLE Forecast-Tage (statt eine E-Mail pro Tag).
        
        Args:
            results_list: Liste von Evaluierungs-Ergebnissen (ein Dict pro Tag)
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
        
        if not results_list:
            return False, "Keine Ergebnisse zu versenden"
        
        try:
            subject = self._create_multi_day_subject(results_list)
            html_body = self._create_multi_day_html_body(results_list)
            text_body = self._create_multi_day_body(results_list)  # Fallback Plain-Text
            
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender
            msg['To'] = self.recipient
            msg['Subject'] = subject
            
            # Plain-Text Version (Fallback)
            msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
            # HTML Version
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))
            
            # SMTP-Versand (gleiche Logik wie send_alert)
            try:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10)
            except Exception as e:
                error_msg = f"Verbindung zum SMTP-Server fehlgeschlagen: {str(e)}"
                logger.error(error_msg)
                if raise_exception:
                    raise ConnectionError(error_msg)
                return False, error_msg
            
            try:
                server.starttls()
                server.login(self.sender, self.password)
                server.send_message(msg)
                server.quit()
            except Exception as e:
                error_msg = f"E-Mail-Versand fehlgeschlagen: {str(e)}"
                logger.error(error_msg)
                server.quit()
                if raise_exception:
                    raise RuntimeError(error_msg)
                return False, error_msg
            
            logger.info(f"Multi-Day E-Mail erfolgreich gesendet für {len(results_list)} Tage")
            return True, None
            
        except Exception as e:
            error_msg = f"Unerwarteter Fehler: {str(e)}"
            logger.error(error_msg)
            if raise_exception:
                raise
            return False, error_msg
    
    def _create_multi_day_subject(self, results_list: list) -> str:
        """Erstellt den E-Mail-Betreff für Multi-Day Forecast."""
        location = results_list[0].get('location', 'Uetliberg')
        num_days = len(results_list)
        return f"🪂 {num_days}-Tages Flug-Forecast - {location}"
    
    def _create_multi_day_body(self, results_list: list) -> str:
        """Erstellt den Plain-Text E-Mail-Body für Multi-Day Forecast."""
        lines = [
            "╔" + "═" * 68 + "╗",
            "║" + " " * 18 + "🪂 FLUGBARKEITS-FORECAST" + " " * 18 + "║",
            "╚" + "═" * 68 + "╝",
            "",
            f"📍 Startplatz: {results_list[0].get('location', 'Uetliberg')}",
            f"📅 Forecast für {len(results_list)} Tage",
            "",
            "━" * 70,
        ]
        
        for i, result in enumerate(results_list, 1):
            date = result.get('date', '')
            conditions = result.get('conditions', 'UNKNOWN')
            flyable = result.get('flyable', False)
            rating = result.get('rating', 0)
            summary = result.get('summary', '')
            
            condition_icon = {'EXCELLENT': '✅', 'GOOD': '✅', 'MODERATE': '⚠️', 'POOR': '❌', 'DANGEROUS': '🚫'}.get(conditions, '❓')
            flyable_text = "FLUGBAR ✅" if flyable else "NICHT FLUGBAR ❌"
            
            lines.extend([
                "",
                f"TAG {i}: {date}",
                "-" * 70,
                f"{condition_icon} Status: {flyable_text} - {conditions}",
                f"⭐ Bewertung: {'⭐' * min(int(rating), 10)} ({rating}/10)",
                f"📝 {summary}",
                "",
            ])
        
        lines.append("━" * 70)
        return "\n".join(lines)
    
    def _create_multi_day_html_body(self, results_list: list) -> str:
        """Erstellt den HTML E-Mail-Body für Multi-Day Forecast."""
        location = results_list[0].get('location', 'Uetliberg')
        
        # Header
        html_parts = [
            """<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flugbarkeits-Forecast</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px 10px 0 0; text-align: center;">
        <h1 style="margin: 0; font-size: 28px;">🪂 FLUGBARKEITS-FORECAST</h1>
        <p style="margin: 10px 0 0 0;">""" + location + """ - """ + str(len(results_list)) + """ Tage</p>
    </div>
    
    <div style="background: white; padding: 30px; border-radius: 0 0 10px 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
"""
        ]
        
        # Tages-Karten
        for i, result in enumerate(results_list, 1):
            date = result.get('date', '')
            conditions = result.get('conditions', 'UNKNOWN')
            flyable = result.get('flyable', False)
            rating = result.get('rating', 0)
            summary = result.get('summary', '')
            details = result.get('details', {})
            
            # Formatiere Datum
            try:
                dt = datetime.strptime(date, "%Y-%m-%d")
                date_str = dt.strftime("%d.%m.%Y")
                weekday = dt.strftime("%A")
                weekday_de = {'Monday': 'Montag', 'Tuesday': 'Dienstag', 'Wednesday': 'Mittwoch',
                            'Thursday': 'Donnerstag', 'Friday': 'Freitag', 'Saturday': 'Samstag', 'Sunday': 'Sonntag'}.get(weekday, weekday)
            except:
                date_str = date
                weekday_de = ""
            
            condition_styles = {
                'EXCELLENT': {'icon': '✅', 'color': '#22c55e', 'bg': '#dcfce7'},
                'GOOD': {'icon': '✅', 'color': '#22c55e', 'bg': '#dcfce7'},
                'MODERATE': {'icon': '⚠️', 'color': '#f59e0b', 'bg': '#fef3c7'},
                'POOR': {'icon': '❌', 'color': '#ef4444', 'bg': '#fee2e2'},
                'DANGEROUS': {'icon': '🚫', 'color': '#dc2626', 'bg': '#fee2e2'}
            }
            style = condition_styles.get(conditions, {'icon': '❓', 'color': '#6b7280', 'bg': '#f3f4f6'})
            
            flyable_text = "FLUGBAR ✅" if flyable else "NICHT FLUGBAR ❌"
            rating_stars = '⭐' * min(int(rating), 10)
            
            html_parts.append(f"""
        <!-- Tag {i} -->
        <div style="margin-bottom: 30px; border: 2px solid {style['color']}; border-radius: 10px; padding: 20px; background: {style['bg']};">
            <h2 style="margin: 0 0 10px 0; color: {style['color']};">TAG {i}: {date_str} ({weekday_de})</h2>
            <div style="font-size: 20px; font-weight: bold; margin-bottom: 15px;">{style['icon']} {flyable_text} - {conditions}</div>
            <div style="margin-bottom: 10px;">⭐ {rating_stars} ({rating}/10)</div>
            <div style="background: white; padding: 15px; border-radius: 6px; margin-top: 15px;">
                <p style="margin: 0; font-weight: 500;">{summary}</p>
            </div>
            <details style="margin-top: 15px;">
                <summary style="cursor: pointer; font-weight: 600; padding: 10px; background: white; border-radius: 6px;">📊 Details anzeigen</summary>
                <div style="margin-top: 10px; padding: 15px; background: white; border-radius: 6px;">
                    <div style="margin-bottom: 10px;"><strong>💨 Wind:</strong> {details.get('wind', 'Nicht verfügbar')}</div>
                    <div style="margin-bottom: 10px;"><strong>☁️ Thermik:</strong> {details.get('thermik', 'Nicht verfügbar')}</div>
                    <div><strong>⚠️ Risiken:</strong> {details.get('risks', 'Nicht verfügbar')}</div>
                </div>
            </details>
        </div>
""")
        
        # Footer
        html_parts.append("""
        <hr style="border: none; border-top: 2px solid #e5e7eb; margin: 30px 0;">
        <div style="text-align: center; color: #6b7280; font-size: 12px;">
            <p style="margin: 5px 0;">📧 Erstellt: """ + datetime.now().strftime('%d.%m.%Y %H:%M:%S') + """</p>
            <p style="margin: 5px 0;">Uetliberg Ticker - Automatische Wetteranalyse</p>
        </div>
    </div>
</body>
</html>
""")
        
        return "".join(html_parts)
    
    def _get_all_recipients(self) -> list:
        """
        Gibt alle Empfaenger zurueck: fester Empfaenger + Subscriber aus InstantDB.
        Jeder Eintrag ist ein Dict mit 'email' und optional 'unsubscribe_token'.
        """
        recipients = [{'email': self.FIXED_RECIPIENT, 'unsubscribe_token': None}]

        try:
            from instantdb_helper import get_all_subscribers
            subscribers = get_all_subscribers()
            for sub in subscribers:
                email = sub.get('email', '').lower()
                if email and email != self.FIXED_RECIPIENT.lower():
                    recipients.append({
                        'email': email,
                        'unsubscribe_token': sub.get('unsubscribe_token')
                    })
        except Exception as e:
            logger.warning(f"Subscriber laden fehlgeschlagen, sende nur an festen Empfaenger: {e}")

        return recipients

    def _add_unsubscribe_footer_html(self, html_body: str, unsubscribe_token: Optional[str]) -> str:
        """Fuegt einen Abmelde-Link am Ende des HTML-Bodys ein."""
        if not unsubscribe_token:
            return html_body

        unsubscribe_url = f"{self.base_url}/unsubscribe/{unsubscribe_token}"
        footer = f'''
        <div style="text-align:center;margin-top:20px;padding-top:15px;border-top:1px solid #e5e7eb;">
            <a href="{unsubscribe_url}" style="color:#6b7280;font-size:11px;text-decoration:underline;">
                E-Mail-Benachrichtigungen abbestellen
            </a>
        </div>'''

        return html_body.replace('</body>', footer + '\n</body>')

    def _add_unsubscribe_footer_text(self, text_body: str, unsubscribe_token: Optional[str]) -> str:
        """Fuegt einen Abmelde-Hinweis am Ende des Plain-Text-Bodys ein."""
        if not unsubscribe_token:
            return text_body

        unsubscribe_url = f"{self.base_url}/unsubscribe/{unsubscribe_token}"
        return text_body + f"\n\n---\nAbmelden: {unsubscribe_url}"

    def send_to_all_subscribers(self, result: Dict, force_send: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Sendet die E-Mail an alle Subscriber (fester Empfaenger + InstantDB).
        """
        if not self.enabled:
            return False, "E-Mail deaktiviert"

        recipients = self._get_all_recipients()
        sent = 0
        errors = []

        subject = self._create_subject(result)
        html_body = self._create_html_body(result)
        text_body = self._create_body(result)

        for recipient in recipients:
            try:
                final_html = self._add_unsubscribe_footer_html(html_body, recipient.get('unsubscribe_token'))
                final_text = self._add_unsubscribe_footer_text(text_body, recipient.get('unsubscribe_token'))

                msg = MIMEMultipart('alternative')
                msg['From'] = self.sender
                msg['To'] = recipient['email']
                msg['Subject'] = subject
                msg.attach(MIMEText(final_text, 'plain', 'utf-8'))
                msg.attach(MIMEText(final_html, 'html', 'utf-8'))

                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10)
                server.starttls()
                server.login(self.sender, self.password)
                server.send_message(msg)
                server.quit()
                sent += 1
                logger.info(f"E-Mail gesendet an {recipient['email']}")
            except Exception as e:
                errors.append(f"{recipient['email']}: {str(e)}")
                logger.error(f"E-Mail an {recipient['email']} fehlgeschlagen: {e}")

        if sent > 0:
            return True, f"{sent}/{len(recipients)} E-Mails gesendet" + (f", Fehler: {'; '.join(errors)}" if errors else "")
        return False, f"Keine E-Mails gesendet. Fehler: {'; '.join(errors)}"

    def send_multi_day_to_all_subscribers(self, results_list: list, force_send: bool = True) -> Tuple[bool, Optional[str]]:
        """
        Sendet die Multi-Day E-Mail an alle Subscriber.
        """
        if not self.enabled:
            return False, "E-Mail deaktiviert"

        recipients = self._get_all_recipients()
        sent = 0
        errors = []

        subject = self._create_multi_day_subject(results_list)
        html_body = self._create_multi_day_html_body(results_list)
        text_body = self._create_multi_day_body(results_list)

        for recipient in recipients:
            try:
                final_html = self._add_unsubscribe_footer_html(html_body, recipient.get('unsubscribe_token'))
                final_text = self._add_unsubscribe_footer_text(text_body, recipient.get('unsubscribe_token'))

                msg = MIMEMultipart('alternative')
                msg['From'] = self.sender
                msg['To'] = recipient['email']
                msg['Subject'] = subject
                msg.attach(MIMEText(final_text, 'plain', 'utf-8'))
                msg.attach(MIMEText(final_html, 'html', 'utf-8'))

                server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10)
                server.starttls()
                server.login(self.sender, self.password)
                server.send_message(msg)
                server.quit()
                sent += 1
            except Exception as e:
                errors.append(f"{recipient['email']}: {str(e)}")
                logger.error(f"Multi-Day E-Mail an {recipient['email']} fehlgeschlagen: {e}")

        if sent > 0:
            return True, f"{sent}/{len(recipients)} E-Mails gesendet"
        return False, f"Keine E-Mails gesendet. Fehler: {'; '.join(errors)}"

    def send_welcome_email(self, email: str, unsubscribe_token: str) -> Tuple[bool, Optional[str]]:
        """Sendet eine Bestaetigungs-E-Mail nach der Anmeldung."""
        if not self.enabled:
            return False, "E-Mail deaktiviert"

        unsubscribe_url = f"{self.base_url}/unsubscribe/{unsubscribe_token}"

        subject = "Willkommen beim Uetliberg Flugwetter-Ticker"

        html_body = f"""<!DOCTYPE html>
<html lang="de">
<head><meta charset="UTF-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;line-height:1.6;color:#333;max-width:600px;margin:0 auto;padding:20px;background:#f5f5f5;">
    <div style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;padding:30px;border-radius:10px 10px 0 0;text-align:center;">
        <h1 style="margin:0;font-size:24px;">Willkommen beim Flugwetter-Ticker</h1>
    </div>
    <div style="background:white;padding:30px;border-radius:0 0 10px 10px;box-shadow:0 2px 10px rgba(0,0,0,0.1);">
        <p>Hallo,</p>
        <p>du hast dich erfolgreich fuer den <strong>Uetliberg Flugwetter-Ticker</strong> angemeldet.</p>
        <p>Ab sofort erhaeltst du automatische E-Mail-Benachrichtigungen mit der aktuellen Flugwetter-Analyse fuer den Uetliberg.</p>
        <div style="background:#f0f9ff;padding:15px;border-radius:8px;border-left:3px solid #667eea;margin:20px 0;">
            <strong>Was du erhaeltst:</strong>
            <ul style="margin:8px 0 0 0;padding-left:20px;">
                <li>Taegliche Flugbarkeits-Bewertung</li>
                <li>Wind-, Thermik- und Risikoanalyse</li>
                <li>Mehrtages-Forecast</li>
            </ul>
        </div>
        <p>Viel Spass und sichere Fluege!</p>
        <hr style="border:none;border-top:1px solid #e5e7eb;margin:25px 0;">
        <div style="text-align:center;">
            <a href="{unsubscribe_url}" style="color:#6b7280;font-size:11px;text-decoration:underline;">
                E-Mail-Benachrichtigungen abbestellen
            </a>
        </div>
    </div>
</body>
</html>"""

        text_body = (
            "Willkommen beim Uetliberg Flugwetter-Ticker\n\n"
            "Du hast dich erfolgreich angemeldet.\n"
            "Ab sofort erhaeltst du automatische E-Mail-Benachrichtigungen "
            "mit der aktuellen Flugwetter-Analyse fuer den Uetliberg.\n\n"
            "Was du erhaeltst:\n"
            "- Taegliche Flugbarkeits-Bewertung\n"
            "- Wind-, Thermik- und Risikoanalyse\n"
            "- Mehrtages-Forecast\n\n"
            "Viel Spass und sichere Fluege!\n\n"
            f"---\nAbmelden: {unsubscribe_url}"
        )

        try:
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender
            msg['To'] = email
            msg['Subject'] = subject
            msg.attach(MIMEText(text_body, 'plain', 'utf-8'))
            msg.attach(MIMEText(html_body, 'html', 'utf-8'))

            server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10)
            server.starttls()
            server.login(self.sender, self.password)
            server.send_message(msg)
            server.quit()
            logger.info(f"Willkommens-E-Mail gesendet an {email}")
            return True, None
        except Exception as e:
            error_msg = f"Willkommens-E-Mail an {email} fehlgeschlagen: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

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

