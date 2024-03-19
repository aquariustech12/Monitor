from flask import Flask, render_template, request, redirect, make_response
import sqlite3
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
import xml.etree.ElementTree as ET
import traceback
import os
import hashlib
import logging

# Configurar el registro de errores
logging.basicConfig(filename='error.log', level=logging.ERROR)

app = Flask(__name__)
app.secret_key = '740212'  # Necesario para usar flash

DATABASE = 'facturas.db'

facturas_pendientes = []

nombre_buque = ''

# Aquí colocamos la función para manejar errores
@app.errorhandler(Exception)
def handle_error(e):
    logging.exception('Ocurrió un error inesperado')
    return 'Ocurrió un error inesperado', 500

@app.route('/')
def index():
    confirmacion = request.args.get('confirmacion')
    response = make_response(render_template('index.html', confirmacion=confirmacion))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/agregar_factura', methods=['POST'])
def agregar_factura():
    conn = None
    try:
        global nombre_buque
        fecha_gasto = request.form['fecha_gasto']
        tipo_comprobante = request.form['tipo_comprobante']
        concepto = request.form['concepto']
        archivo_factura = request.files['archivo_factura']
        nombre_buque = request.form['nombre_buque']
        monto_aprobado = request.form['monto_aprobado']
        observaciones = request.form['observaciones']

        if not os.path.exists(nombre_buque):
            os.makedirs(nombre_buque)

        conn = sqlite3.connect(f'{nombre_buque}/{nombre_buque}_facturas.db')
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS facturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre_buque TEXT,
                fecha_gasto TEXT,
                tipo_comprobante TEXT,
                concepto TEXT,
                rfc_emisor TEXT,
                razon_social_emisor TEXT,
                folio TEXT,
                subtotal REAL,
                iva REAL,
                total REAL,
                monto_aprobado REAL,
                observaciones TEXT,
                sello TEXT
            )
        ''')

        cursor.execute("PRAGMA table_info(facturas)")
        columns = cursor.fetchall()
        column_names = [column[1] for column in columns]

        if 'nombre_buque' not in column_names:
            cursor.execute("ALTER TABLE facturas ADD COLUMN nombre_buque TEXT")
        if 'fecha_gasto' not in column_names:
            cursor.execute("ALTER TABLE facturas ADD COLUMN fecha_gasto TEXT")
        if 'tipo_comprobante' not in column_names:
            cursor.execute("ALTER TABLE facturas ADD COLUMN tipo_comprobante TEXT")
        if 'concepto' not in column_names:
            cursor.execute("ALTER TABLE facturas ADD COLUMN concepto TEXT")
        if 'monto_aprobado' not in column_names:
            cursor.execute("ALTER TABLE facturas ADD COLUMN monto_aprobado TEXT")
        if 'observaciones' not in column_names:
            cursor.execute("ALTER TABLE facturas ADD COLUMN observaciones TEXT")
        if 'sello' not in column_names:
            cursor.execute("ALTER TABLE facturas ADD COLUMN sello TEXT")

        tree = ET.parse(archivo_factura)
        root = tree.getroot()
        
        emisor = root.find(".//cfdi:Emisor", namespaces={'cfdi': 'http://www.sat.gob.mx/cfd/4'})

        if emisor is not None:
            rfc_emisor = emisor.get("Rfc", "")
            razon_social_emisor = emisor.get("Nombre", "")
            folio = root.get("Folio", "")
            sello = root.get("Sello", "")
            subtotal = float(root.get("SubTotal", 0))
            iva = float(root.find(".//cfdi:Traslado", namespaces={'cfdi': 'http://www.sat.gob.mx/cfd/4'}).get("Importe", 0))
            total = float(root.get("Total", 0))
            monto_aprobado = total
        
            # Verifica si el documento ya existe en la base de datos
            cursor.execute("SELECT * FROM facturas WHERE sello = ?", (sello,))
            documento_existente = cursor.fetchone()

        if documento_existente is not None:
            return f"Error: El documento con el número de sello {sello} ya existe en la base de datos."
        else:
            cursor.execute('''
                INSERT INTO facturas (nombre_buque, fecha_gasto, tipo_comprobante, concepto, rfc_emisor, razon_social_emisor, folio, subtotal, iva, total, monto_aprobado, observaciones, sello)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (nombre_buque, fecha_gasto, tipo_comprobante, concepto, rfc_emisor, razon_social_emisor, folio, subtotal, iva, total, monto_aprobado, observaciones, sello))

            conn.commit()
            facturas_pendientes.append({
                'nombre_buque': nombre_buque,
                'fecha_gasto': fecha_gasto,
                'tipo_comprobante': tipo_comprobante,
                'concepto': concepto,
                'rfc_emisor': rfc_emisor,
                'razon_social_emisor': razon_social_emisor,
                'folio': folio,
                'subtotal': subtotal,
                'iva': iva,
                'total': total,
                'monto_aprobado': monto_aprobado,
                'observaciones': observaciones,
                'sello': sello
            })
            return redirect(f'/?confirmacion=Factura+agregada+correctamente+para+{nombre_buque}.')
        
    except Exception as e:
        return f"Error: {str(e)}, traceback: {traceback.format_exc()}"
    finally:
        if conn is not None:
            conn.close()
        else:
            return "Error: No se pudo establecer una conexión con la base de datos."

@app.route('/enviar_facturas', methods=['POST'])
def enviar_facturas():
    conn = None
    try:
        facturas = facturas_pendientes.copy()
        facturas_pendientes.clear()

        if not facturas:
            return "No hay facturas para enviar."

        conn = sqlite3.connect(f'{nombre_buque}/{nombre_buque}_facturas.db')
        df = pd.DataFrame(facturas)
        df.to_sql('facturas_temp', conn, index=False, if_exists='replace')

        excel_file = f'informe_gastos_{nombre_buque}.xlsx'
        df.to_excel(excel_file, index=False)

        enviar_correo(excel_file, nombre_buque)
        return render_template('confirmacion.html', nombre_buque=nombre_buque)

    except Exception as e:
        return f"Error al enviar facturas: {str(e)}"
    finally:
        if conn is not None:
            conn.close()

@app.route('/formulario_nota', methods=['GET'])
def formulario_nota():
    confirmacion = request.args.get('confirmacion')
    response = make_response(render_template('form.html', confirmacion=confirmacion))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    return response

@app.route('/formulario_nota', methods=['POST'])
def form_to_xml():
    # Obtén los datos del formulario
    nombre_buque = request.form['nombre_buque']
    rfc_emisor = request.form.get('rfc_emisor')
    razon_social_emisor = request.form.get('razon_social_emisor')
    folio = request.form.get('folio')
    subtotal = request.form.get('subtotal')
    iva = request.form.get('iva')
    total = request.form.get('total')
    
    # Genera un identificador único para la nota
    nota_content = nombre_buque + rfc_emisor + razon_social_emisor + folio + subtotal + iva + total
    Sello = hashlib.sha256(nota_content.encode()).hexdigest()

    # Crea el archivo XML
    root = ET.Element('cfdi:Comprobante', {
        'xmlns:cfdi': 'http://www.sat.gob.mx/cfd/4',
        'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
        'Version': '4.0',
        'SubTotal': subtotal,
        'Moneda': 'MXN',
        'Total': total,
        'TipoDeComprobante': 'I',
        'MetodoPago': 'PUE',
        'Folio': folio,
        'Sello': Sello,
    })

    emisor = ET.SubElement(root, 'cfdi:Emisor', {
        'Rfc': rfc_emisor,
        'Nombre': razon_social_emisor,
    })

    print(f"Folio: {folio}")

    # Crea el elemento 'cfdi:Traslado' y agrégalo al XML
    traslados = ET.SubElement(root, 'cfdi:Traslados')
    traslados = ET.SubElement(traslados, 'cfdi:Traslado', {
        'Base': subtotal,
        'Impuesto': '002',
        'TipoFactor': 'Tasa',
        'TasaOCuota': '0.160000',
        'Importe': iva,
    })
    # Aquí puedes agregar más elementos y atributos según sea necesario
    xml_str = ET.tostring(root, encoding='utf-8')
    response = make_response(xml_str)
    response.headers['Content-Disposition'] = 'attachment; filename=nota_de_consumo.xml'
    response.headers['Content-Type'] = 'application/xml'
    response.set_cookie('fileDownloadToken', request.form.get('fileDownloadToken'))

    return response

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '-1'
    return response

def enviar_correo(archivo_adjunto, nombre_buque):
    try:
        from_email = 'marketingconsultantsmx@gmail.com'
        to_email = 'generalmanager@maritimeprotection.mx'

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, 'phyjhuxbhmmpuhvi')

        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = f'Informe de Gastos - {nombre_buque}'

        with open(archivo_adjunto, 'rb') as file:
            attachment = MIMEApplication(file.read(), _subtype="xlsx")
            attachment.add_header('Content-Disposition', 'attachment', filename=f'informe_gastos_{nombre_buque}.xlsx')
            msg.attach(attachment)

        server.send_message(msg)
        server.quit()

    except Exception as e:
        print(f"Error enviando correo: {str(e)}")

if __name__ == '__main__':
    app.run(debug=True)
