"""
Vercel Serverless Function für das Web-Interface
"""

import sys
import os
import io
from pathlib import Path

# Flask-App initialisieren
try:
    # Füge Projekt-Root zum Python-Pfad hinzu
    project_root = Path(__file__).parent.parent
    sys.path.insert(0, str(project_root))
    
    # Stelle sicher, dass Flask das templates-Verzeichnis findet
    # Wichtig: Vercel ändert das Arbeitsverzeichnis, daher verwenden wir absoluten Pfad
    original_cwd = os.getcwd()
    os.chdir(str(project_root))
    
    # Prüfe ob templates-Verzeichnis existiert
    templates_dir = project_root / 'templates'
    if not templates_dir.exists():
        print(f"WARNUNG: templates-Verzeichnis nicht gefunden: {templates_dir}")
    
    from web import app
    
except Exception as e:
    # Fehlerbehandlung für bessere Debugging-Informationen
    import traceback
    error_msg = f"Fehler beim Initialisieren der Flask-App: {str(e)}\n{traceback.format_exc()}"
    print(error_msg)
    
    # Erstelle einen minimalen Error-Handler
    from flask import Flask
    app = Flask(__name__)
    
    @app.route('/')
    @app.route('/<path:path>')
    def error_handler(path=''):
        return f"<h1>Fehler beim Laden der Anwendung</h1><pre>{error_msg}</pre>", 500


def handler(request):
    """
    Vercel Serverless Function Handler für Flask-App.
    
    Konvertiert Vercel's Request-Objekt zu WSGI-Umgebung und ruft Flask-App auf.
    
    Args:
        request: Vercel Request-Objekt (kann dict oder Objekt sein)
    
    Returns:
        Vercel Response-Objekt mit statusCode, headers, body
    """
    try:
        # Handle verschiedene Request-Formate (dict oder Objekt)
        if isinstance(request, dict):
            method = request.get('method', 'GET')
            url = request.get('url', '/')
            headers = request.get('headers', {})
            body = request.get('body', b'')
        else:
            method = getattr(request, 'method', 'GET')
            url = getattr(request, 'url', '/')
            headers = getattr(request, 'headers', {})
            body = getattr(request, 'body', b'')
        
        # Parse URL
        if isinstance(url, str):
            url_parts = url.split('?', 1)
            path_info = url_parts[0] or '/'
            query_string = url_parts[1] if len(url_parts) > 1 else ''
        else:
            path_info = getattr(url, 'path', '/')
            query_string = getattr(url, 'query', '')
        
        # Konvertiere Body zu Bytes falls nötig
        if isinstance(body, str):
            body = body.encode('utf-8')
        elif body is None:
            body = b''
        
        # Erstelle WSGI-Umgebungsvariablen
        environ = {
            'REQUEST_METHOD': method or 'GET',
            'SCRIPT_NAME': '',
            'PATH_INFO': path_info,
            'QUERY_STRING': query_string,
            'CONTENT_TYPE': headers.get('content-type', ''),
            'CONTENT_LENGTH': str(len(body)),
            'SERVER_NAME': headers.get('host', 'localhost').split(':')[0],
            'SERVER_PORT': headers.get('host', 'localhost').split(':')[1] if ':' in headers.get('host', '') else '443',
            'SERVER_PROTOCOL': 'HTTP/1.1',
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': headers.get('x-forwarded-proto', 'https'),
            'wsgi.input': io.BytesIO(body),
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': True,
            'wsgi.run_once': False,
        }
        
        # Füge HTTP-Header hinzu
        for key, value in headers.items():
            key = key.upper().replace('-', '_')
            if key not in ('CONTENT_TYPE', 'CONTENT_LENGTH'):
                environ[f'HTTP_{key}'] = str(value)
        
        # Rufe Flask-App als WSGI-App auf
        response_data = []
        status_code = [200]
        response_headers = []
        
        def start_response(status, response_headers_list):
            status_code[0] = int(status.split()[0])
            response_headers.extend(response_headers_list)
        
        # WSGI-App aufrufen
        response_iter = app(environ, start_response)
        
        # Response-Daten sammeln
        try:
            for data in response_iter:
                if isinstance(data, str):
                    response_data.append(data.encode('utf-8'))
                else:
                    response_data.append(data)
        finally:
            if hasattr(response_iter, 'close'):
                response_iter.close()
        
        # Konvertiere zu Vercel Response-Format
        body_bytes = b''.join(response_data)
        try:
            body_str = body_bytes.decode('utf-8')
        except UnicodeDecodeError:
            body_str = body_bytes.decode('latin-1')
        
        headers_dict = {key: value for key, value in response_headers}
        
        return {
            'statusCode': status_code[0],
            'headers': headers_dict,
            'body': body_str
        }
        
    except Exception as e:
        import traceback
        error_msg = f"Fehler im Handler: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'text/html; charset=utf-8'},
            'body': f"<h1>Internal Server Error</h1><pre>{error_msg}</pre>"
        }

