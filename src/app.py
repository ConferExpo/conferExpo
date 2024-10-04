import io
import cv2
from flask import Flask, jsonify, make_response, render_template, request, redirect, url_for, flash, send_file, send_from_directory
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask import send_from_directory, abort
import os
from dotenv import load_dotenv
import numpy as np
from pymongo import MongoClient
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SubmitField, StringField, TextAreaField, DateTimeField
from wtforms.validators import DataRequired, Optional
from datetime import datetime, timedelta
import qrcode

from config import config

# Models:
from models.ModelUser import ModelUser
from models.ModelEvento import ModelEvento

# Entities:
from models.entities.User import User
from models.entities.Evento import Evento
load_dotenv()

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

IMG_FOLDER = os.path.join("public", "imgEvent")

app.config["UPLOAD_FOLDER"] = IMG_FOLDER

csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # Vista a la que se redirigirá si el usuario no está autenticado
login_manager.session_protection = "strong"  # Usar protección de sesión "strong" para detectar cambios de IP

# Duración de la sesión
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=20)  # Sesión expira después de 30 minutos de inactividad

# Configuración de MongoDB
mongo_uri = os.environ.get('MONGO_URI')
client = MongoClient(mongo_uri)
db = client.asistenciaWeb_2024


@login_manager.user_loader
def load_user(id):
    return ModelUser.get_by_id(db, id)

@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # Obtener los datos del formulario de registro
        username = request.form['username']
        password = request.form['password']
        nombre = request.form['nombre']
        matricula = request.form['matricula']
        telefono = request.form['telefono']
        correo_electronico = request.form['correo_electronico']
        motivo_prof = request.form['motivo_prof']
        # Otros campos...

        # Verificar si el nombre de usuario ya está en uso
        if ModelUser.get_by_username(db, username):
            flash('El nombre de usuario ya está en uso. Por favor, elige otro.')
            return redirect(url_for('register'))

        # Verificar si el correo electrónico ya está en uso
        if ModelUser.get_by_email(db, correo_electronico):
            flash('El correo electrónico ya está en uso. Por favor, utiliza otro.')
            return redirect(url_for('register'))

        # Crear un nuevo usuario
        new_user = User(username=username, password=password, nombre=nombre, matricula=matricula, telefono=telefono, correo_electronico=correo_electronico, motivo_prof=motivo_prof, rol='usuario')
        # Otros campos...

        # Guardar el nuevo usuario en la base de datos
        ModelUser.register(db, new_user)

        flash('¡Registro exitoso! Por favor, inicia sesión.')
        return redirect(url_for('login'))
    else:
        return render_template('auth/register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User(0, request.form['username'], request.form['password'])
        logged_user = ModelUser.login(db, user)
        if logged_user:
            login_user(logged_user)
            if logged_user.rol == 'administrador': 
                return redirect(url_for('homeAdmin'))
            elif logged_user.rol == 'usuario':
                return redirect(url_for('homeUser'))
            else:
                flash("Usuario o contraseña no válidos")
                return render_template('auth/login.html')
        else:
            flash("Usuario o contraseña no válidos")
            return render_template('auth/login.html')
    else:
        return render_template('auth/login.html')

@app.route('/homeUser')
@login_required
def homeUser():
    if current_user.rol == "usuario":
        nombre_usuario = current_user.username
        # Obtener todos los eventos
        eventos, mensaje = ModelEvento.get_all_eventos_proximos_fecha_hora_inicio(db)

        if eventos is None:
            return render_template("userConferExpo/homeUser.html", error=mensaje)

        return render_template("userConferExpo/homeUser.html", eventos=eventos, nombre_usuario=nombre_usuario)
    else:
        #abort(404)
        return render_template('error/404.html'), 404

@app.route('/showEventUser/<_id>', methods=['GET', 'POST'])
@login_required
def showEventUser(_id):
    if current_user.rol == "usuario":
        nombre_usuario = current_user.username
        nombre_usuario_id = current_user.id
        if request.method == 'GET':
            eventoID = ModelEvento.get_evento_by_id_user(db, _id)
            if not eventoID:
                flash('El evento no existe', 'error')
                return redirect(url_for('homeUser'))

            # Convertimos la fecha al formato deseado
            fecha = datetime.strptime(eventoID.fecha, "%Y-%m-%d")
            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
            nombre_dia_semana = dias_semana[fecha.weekday()]
            nombre_mes = meses[fecha.month - 1]
            fecha_formateada = f"{nombre_dia_semana}, {fecha.day} de {nombre_mes} de {fecha.year}"
            # Obtenemos el número de usuarios registrados
            num_usuarios_registrados = len(eventoID.usuarios_registrados)
            # Convertimos el aforo a un entero
            aforo = int(eventoID.aforo)
             # Calculamos la disponibilidad
            disponibilidad = aforo - len(eventoID.usuarios_registrados)
            # Convertir la fecha y hora del evento a un objeto datetime
            fecha_evento = eventoID.fecha + ' ' + eventoID.fecha_hora_inicio
            fecha_evento_datetime = datetime.strptime(fecha_evento, '%Y-%m-%d %H:%M')

            # Obtener la fecha y hora actual
            fecha_actual = datetime.now()

            # Calcular el tiempo restante
            tiempo_restante = fecha_evento_datetime - fecha_actual

            # Dividir el tiempo restante en días, horas, minutos y segundos
            dias_restantes = tiempo_restante.days
            horas_restantes, segundos_restantes = divmod(tiempo_restante.seconds, 3600)
            minutos_restantes, segundos_restantes = divmod(segundos_restantes, 60)
            hora_inicio, minutos_inicio = eventoID.fecha_hora_inicio.split(':')
            fecha_hora_inicio = {'hora': int(hora_inicio), 'minutos': int(minutos_inicio)}
            # Obtener el año, mes y día de la fecha
            year = fecha.year
            month = fecha.month
            day = fecha.day
            # Verificar si el usuario ya está registrado para este evento
            if nombre_usuario_id in eventoID.usuarios_registrados:
                registrado = 1
            else:
                registrado = 0

            return render_template('userConferExpo/showEventUser.html', eventoID=eventoID, fecha_formateada=fecha_formateada, num_usuarios_registrados=num_usuarios_registrados, disponibilidad=disponibilidad,dias_restantes=dias_restantes, horas_restantes=horas_restantes, minutos_restantes=minutos_restantes, segundos_restantes=segundos_restantes, fecha_hora_inicio=fecha_hora_inicio, year=year, month=month, day=day, nombre_usuario=nombre_usuario, registrado=registrado)
        else:
            #abort(404)
            return render_template('error/404.html'), 404
    
@app.route('/assistEvent/<evento_id>', methods=['POST'])
@login_required
def assistEvent(evento_id):
    # Obtener el ID del usuario loggeado
    user_id = current_user.id
    
    # Verificar si se recibió una solicitud POST
    if request.method == 'POST':
        # Obtener el evento por su ID utilizando el método del modelo
        evento = ModelEvento.get_evento_by_id(db, evento_id)

        # Verificar si se encontró el evento
        if evento:
            # Verificar si hay lugares disponibles para el evento
            aforo = int(evento.aforo)
            if aforo <= len(evento.usuarios_registrados):
                flash('No hay lugares disponibles para este evento.', 'error')
            else:
                # Registrar al usuario para el evento
                #evento.registrar_usuario(user_id)
                # Actualizar el evento en la base de datos
                success, message = ModelEvento.update_evento_assist(db, evento_id, user_id)
                if success:
                    # Agregar el evento a la lista de eventos por asistir del usuario
                    success_user, message_user = ModelUser.update_usuario_assist(db, user_id, evento_id)
                    if success_user:
                        flash('Te has registrado correctamente para el evento.', 'success')
                    else:
                        flash(f'Error al actualizar eventos por asistir para el usuario: {message_user}', 'error')
                else:
                    flash(f'Error al registrar para el evento: {message}', 'error')
        else:
            flash('El evento no existe.', 'error')

    # Redirigir de vuelta a la página de inicio o a donde desees
    return redirect(url_for('homeUser'))


@app.route('/asistidosUser')
@login_required
def asistidosUser():
    if current_user.rol == "usuario":
        nombre_usuario = current_user.username
        user_id = current_user.id
        # Obtener todos los eventos asistidos
        eventos_asistidos = ModelUser.get_all_eventos_asistidos(db, user_id)

        if eventos_asistidos is None:
            mensaje = "Error al obtener eventos asistidos."
            return render_template("userConferExpo/asistidosUser.html", error=mensaje)  # Asumo que tienes una plantilla 'asistidosUser.html'

        return render_template("userConferExpo/asistidosUser.html", eventos=eventos_asistidos, nombre_usuario=nombre_usuario)
    else:
        #abort(404)
        return render_template('error/404.html'), 404


@app.route('/assistUserList')
@login_required
def assistUserList():
    if current_user.rol == "usuario":
        nombre_usuario = current_user.username
        user_id = current_user.id
        # Obtener todos los eventos
        #eventos, mensaje = ModelEvento.get_all_eventos_by_user(db, user_id)
        eventos_por_assistir = ModelUser.get_all_eventos_por_assistir_by_user(db, user_id)

        if eventos_por_assistir is None:
            mensaje = "Error al obtener eventos por asistir."
            return render_template("userConferExpo/assistUserList.html", error=mensaje)

        return render_template("userConferExpo/assistUserList.html", eventos=eventos_por_assistir, nombre_usuario=nombre_usuario)
    else:
        #abort(404)
        return render_template('error/404.html'), 404



# Ruta para generar el código QR
@app.route('/generate_qr/<user_id>/<event_id>')
def generate_qr(user_id, event_id):
    # Crear la cadena de datos que deseas codificar en el código QR
    qr_data = f"Usuario: {user_id}, Evento: {event_id}"

    # Crear el objeto QRCode y generar el código QR
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)

    # Crear una imagen PIL del código QR
    qr_image = qr.make_image(fill_color="black", back_color="white")

    # Convertir la imagen del código QR en bytes
    img_bytes = io.BytesIO()
    qr_image.save(img_bytes, format='PNG')
    img_bytes.seek(0)

    # Crear una respuesta con la imagen del código QR
    response = make_response(img_bytes.getvalue())
    response.headers['Content-Type'] = 'image/png'

    return response

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/home')
@login_required
def home():
    return render_template('home.html')

@app.route("/homeAdmin")
@login_required
def homeAdmin():
    # Verificar el rol del usuario
    if current_user.rol == "administrador":
        nombre_usuario = current_user.username
        # Obtener todos los eventos
        eventos, mensaje = ModelEvento.get_all_eventos(db)

        if eventos is None:
            return render_template("adminUser/homeAdmin.html", error=mensaje)

        return render_template("adminUser/homeAdmin.html", eventos=eventos, nombre_usuario=nombre_usuario)
    else:
        # Si el usuario no es un administrador, redirigir a una página de error 404
        #abort(404)
        return render_template('error/404.html'), 404



def allowed_file(filename):
    allowed_extensions = app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

@app.route('/newEvent')
@login_required
def newEvent():
    # Verificar el rol del usuario
    if current_user.rol == "administrador":
        nombre_usuario = current_user.username
        return render_template('adminUser/newEvent.html', nombre_usuario=nombre_usuario)
    else:
        # Si el usuario no es un administrador, redirigir a una página de error 404
        #abort(404)
        return render_template('error/404.html'), 404


@app.route('/registerEvent', methods=['GET', 'POST'])
@login_required
def registerEvent():
    if current_user.rol == "administrador":
        if request.method == 'POST':
            # Obtener los datos del formulario de registro
            nombre = request.form['eventName']
            resumen = request.form['resumeEvent']
            fecha = request.form['dateEvent']
            fecha_hora_inicio = request.form['starHour']
            fecha_hora_fin = request.form['finishHour']
            lugar = request.form['addressEvent']
            referencias = request.form['referencesAddress']
            aforo = request.form['aforo']
            duracion_estimada = request.form['duracion_estimada']
            descripcion = request.form['descriptionEvent']
            estatus_evento = 0

            # Verificar si se ha proporcionado una imagen
            if 'imagen' not in request.files:
                flash('No se ha proporcionado ninguna imagen')
                return redirect(request.url)

            imagen = request.files['imagen']


            # Verificar si la imagen tiene un nombre de archivo válido
            if imagen.filename == '':
                flash('No se ha seleccionado ningún archivo')
                return redirect(request.url)

            if imagen and allowed_file(imagen.filename):
                # Se asegura que el nombre del archivo sea seguro
                filename = secure_filename(imagen.filename)
                # Se guarda la imagen en la carpeta deseada
                imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            else:
                flash('El formato de archivo de imagen no es válido')
                return redirect(request.url)

            # Crear un nuevo evento
            new_event = Evento(
                nombre=nombre,
                resumen=resumen,
                fecha = fecha,
                fecha_hora_inicio=fecha_hora_inicio,
                fecha_hora_fin=fecha_hora_fin,
                lugar=lugar,
                referencias=referencias,
                aforo=aforo,
                duracion_estimada=duracion_estimada,
                descripcion=descripcion,
                estatus_evento=estatus_evento,
                imagen=filename
                #imagen=os.path.join(app.config['UPLOAD_FOLDER'], filename)
            )

            # Guardar el nuevo evento en la base de datos
            success, message = ModelEvento.crear_evento(db, new_event)

            if success:
                flash(message)
                return redirect(url_for('homeAdmin'))
            else:
                flash(message, 'error')
                return redirect(url_for('registerEvent'))
        else:
            return render_template('adminUser/newEvent.html')
    else:
        #abort(404)
        return render_template('error/404.html'), 404
    
@app.route('/mostrar_imagen/<filename>')
def mostrar_imagen(filename):
    try:
        # Suponiendo que tienes una carpeta llamada 'public/imgEvent' donde guardas tus imágenes
        # y que 'UPLOAD_FOLDER' está configurado correctamente en tu configuración
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except FileNotFoundError:
        # Si no se encuentra el archivo, regresa un error 404
        #abort(404)
        return render_template('error/404.html'), 404
    
        
@app.route('/show_image/<filename>')
def show_image(filename):
    upload_folder = app.config['UPLOAD_FOLDER']
    image_path = os.path.join(upload_folder, filename)
    
    # Verifica si la imagen existe en la ubicación especificada
    if os.path.isfile(image_path):
        return send_from_directory(upload_folder, filename)
    else:
        # Si la imagen no existe, devuelve la imagen por defecto
        default_image_path = os.path.join(app.static_folder, 'img', 'confer_default.jpg')
        return send_file(default_image_path)

    
@app.route('/showEvent/<_id>', methods=['GET', 'POST'])
@login_required
def showEvent(_id):
    if current_user.rol == "administrador":
        nombre_usuario = current_user.username
        if request.method == 'GET':
            eventoID = ModelEvento.get_evento_by_id_user(db, _id)
            if not eventoID:
                flash('El evento no existe', 'error')
                return redirect(url_for('homeAdmin'))

            # Convertimos la fecha al formato deseado
            fecha = datetime.strptime(eventoID.fecha, "%Y-%m-%d")
            dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
            meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
            nombre_dia_semana = dias_semana[fecha.weekday()]
            nombre_mes = meses[fecha.month - 1]
            fecha_formateada = f"{nombre_dia_semana}, {fecha.day} de {nombre_mes} de {fecha.year}"
            # Obtenemos el número de usuarios registrados
            num_usuarios_registrados = len(eventoID.usuarios_registrados)
            # Convertimos el aforo a un entero
            aforo = int(eventoID.aforo)
             # Calculamos la disponibilidad
            disponibilidad = aforo - len(eventoID.usuarios_registrados)
            # Convertir la fecha y hora del evento a un objeto datetime
            fecha_evento = eventoID.fecha + ' ' + eventoID.fecha_hora_inicio
            fecha_evento_datetime = datetime.strptime(fecha_evento, '%Y-%m-%d %H:%M')

            # Obtener la fecha y hora actual
            fecha_actual = datetime.now()

            # Calcular el tiempo restante
            tiempo_restante = fecha_evento_datetime - fecha_actual

            # Dividir el tiempo restante en días, horas, minutos y segundos
            dias_restantes = tiempo_restante.days
            horas_restantes, segundos_restantes = divmod(tiempo_restante.seconds, 3600)
            minutos_restantes, segundos_restantes = divmod(segundos_restantes, 60)
            hora_inicio, minutos_inicio = eventoID.fecha_hora_inicio.split(':')
            fecha_hora_inicio = {'hora': int(hora_inicio), 'minutos': int(minutos_inicio)}
            # Obtener el año, mes y día de la fecha
            year = fecha.year
            month = fecha.month
            day = fecha.day

            return render_template('adminUser/showEvent.html', eventoID=eventoID, fecha_formateada=fecha_formateada, num_usuarios_registrados=num_usuarios_registrados, disponibilidad=disponibilidad,dias_restantes=dias_restantes, horas_restantes=horas_restantes, minutos_restantes=minutos_restantes, segundos_restantes=segundos_restantes, fecha_hora_inicio=fecha_hora_inicio, year=year, month=month, day=day, nombre_usuario=nombre_usuario)
        else:
            #abort(401)
            return render_template('error/404.html'), 404
   
@app.route('/editarEvento/<_id>', methods=['GET', 'POST'])
@login_required
def editarEvento(_id):
    if current_user.rol == "administrador":
        nombre_usuario = current_user.username
        if request.method == 'GET':
            resultData = ModelEvento.get_evento_by_id(db, _id)
            if not resultData:
                flash('El evento no existe', 'error')
                return redirect(url_for('homeAdmin'))
            return render_template('adminUser/editEvent.html', eventoID=resultData, nombre_usuario=nombre_usuario)

        if request.method == 'POST':
            # Obtener el evento de la base de datos antes de la edición
            evento_anterior = ModelEvento.get_evento_by_id(db, _id)
            if not evento_anterior:
                flash('El evento no existe', 'error')
                return redirect(url_for('homeAdmin'))

            # Guardar la información de usuarios registrados antes de la edición
            usuarios_registrados_anteriores = evento_anterior.usuarios_registrados

            # Obtener los datos del formulario
            nombre = request.form['eventName']
            resumen = request.form['resumeEvent']
            fecha = request.form['dateEvent']
            fecha_hora_inicio = request.form['starHour']
            fecha_hora_fin = request.form['finishHour']
            lugar = request.form['addressEvent']
            referencias = request.form['referencesAddress']
            aforo = request.form['aforo']
            duracion_estimada = request.form['duracion_estimada']
            descripcion = request.form['descriptionEvent']
            estatus_evento = evento_anterior.estatus_evento

            # Validar datos e imagen (similar al código de 'registerEvent')
            imagen = request.files['imagen']
            # Verificar si se proporcionó una nueva imagen
            if imagen and imagen.filename != '':
                if allowed_file(imagen.filename):
                    # Se asegura que el nombre del archivo sea seguro
                    filename = secure_filename(imagen.filename)
                    # Se guarda la nueva imagen en la carpeta deseada
                    imagen.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    # Actualizar la imagen en el evento solo si se proporciona una nueva imagen
                    evento_anterior.imagen = filename
                else:
                    flash('El formato de archivo de imagen no es válido')
                    return redirect(request.url)

            # Actualizar los campos del evento
            evento_anterior.nombre = nombre
            evento_anterior.resumen = resumen
            evento_anterior.fecha = fecha
            evento_anterior.fecha_hora_inicio = fecha_hora_inicio
            evento_anterior.fecha_hora_fin = fecha_hora_fin
            evento_anterior.lugar = lugar
            evento_anterior.referencias = referencias
            evento_anterior.aforo = aforo
            evento_anterior.duracion_estimada = duracion_estimada
            evento_anterior.descripcion = descripcion
            evento_anterior.estatus_evento = estatus_evento

            # Restaurar la información de usuarios registrados
            evento_anterior.usuarios_registrados = usuarios_registrados_anteriores

            # Actualizar el evento en la base de datos
            success, message = ModelEvento.update_evento(db, _id, evento_anterior)

            if success:
                flash(message)
                return redirect(url_for('homeAdmin'))
            else:
                flash(message, 'error')
                return redirect(url_for('editarEvento', _id=_id))
    else:
        return render_template('error/404.html'), 404


@app.route("/scan_qr_event")
@login_required
def scan_qr_event():
    # Verificar el rol del usuario
    if current_user.rol == "administrador":
        nombre_usuario = current_user.username
        # Obtener todos los eventos
        eventos, mensaje = ModelEvento.get_all_eventos(db)

        if eventos is None:
            return render_template("adminUser/scan_qr_event.html", error=mensaje)

        return render_template("adminUser/scan_qr_event.html", eventos=eventos, nombre_usuario=nombre_usuario)
    else:
        # Si el usuario no es un administrador, redirigir a una página de error 404
        #abort(404)
        return render_template('error/404.html'), 404
        
@app.route("/process_qr_code", methods=["POST"])
def process_qr_code():
    # Obtener los datos del código QR escaneado desde la solicitud POST
    qr_data = request.json.get("qr_data")

    # Analizar la cadena del código QR para obtener los datos del usuario y del evento
    user_id = None
    event_id = None
    if qr_data:
        # Dividir la cadena del código QR en partes usando la coma como separador
        parts = qr_data.split(", ")

        # Iterar sobre las partes y extraer los datos del usuario y del evento
        for part in parts:
            if part.startswith("Usuario:"):
                user_id = part.split(":")[1].strip()
            elif part.startswith("Evento:"):
                event_id = part.split(":")[1].strip()

    # Verificar si se obtuvieron los datos del usuario y del evento
    if user_id is None or event_id is None:
        # Si falta alguno de los datos, devolver un mensaje de error
        response_data = {
            "error_message": "No se pudieron obtener los datos del código QR",
            "success_message":"No se pudieron obtener los datos del código QR"
        }
        return jsonify(response_data)  # Código de estado 400 para solicitud incorrecta

    # Verificar si el usuario ya está registrado para el evento
    if not ModelUser.busca_evento_usuario(db, user_id, event_id):
        # Si el usuario no está registrado, proceder con la actualización en la base de datos
        if ModelUser.update_eventos_asistidos(db, user_id, event_id):
            ModelEvento.register_user_assist_event(db, user_id, event_id)
            # Preparar la respuesta JSON con los datos del usuario y del evento, así como el mensaje de éxito
            ModelUser.delete_evento_asistido_by_user(db, user_id, event_id)
            response_data = {
                "user_id": user_id,
                "event_id": event_id,
                "success_message": "El usuario fue registrado con éxito ;)"
            }
            return jsonify(response_data)
        else:
            # Si hay un error al actualizar la base de datos, devolver un mensaje de error
            response_data = {
                "error_message": "Error al procesar el código QR, inténtalo de nuevo más tarde",
                "success_message":"Error al procesar el código QR, inténtalo de nuevo más tarde"
            }
            return jsonify(response_data)  # Código de estado 500 para error interno del servidor
    else:
        # Si el usuario ya está registrado, devolver un mensaje de error
        response_data = {
            "error_message": "El usuario ya está registrado para este evento",
            "success_message":"El usuario ya está registrado para este evento"
        }
        return jsonify(response_data)  # Código de estado 400 para solicitud incorrecta
    
@app.route('/usersList' , methods=['GET', 'POST'])
@login_required
def usersList():
    if current_user.rol == "administrador":
        nombre_usuario = current_user.username
        users, mensaje = ModelUser.get_all_user(db)
        if users is None:
            return render_template("adminUser/usersList.html", error=mensaje)
        
        return render_template('adminUser/usersList.html',users=users, nombre_usuario=nombre_usuario)
    else:
        # Si el usuario no es un administrador, redirigir a una página de error 404
        #abort(404)
        return render_template('error/404.html'), 404      
    
@app.route('/cancelEvent/<evento_id>', methods=['POST'])
@login_required
def cancelEvent(evento_id):
    # Obtener el ID del usuario loggeado
    user_id = current_user.id
    
    # Verificar si se recibió una solicitud POST
    if request.method == 'POST':
        # Intentar cancelar el evento
        success, message = ModelEvento.update_cancel_event(db, evento_id)

        if success:
            flash('El evento ha sido cancelado correctamente.', 'success')
        else:
            flash(f'Error al cancelar el evento: {message}', 'error')

    # Redirigir de vuelta a la página de inicio o a donde desees
    return redirect(url_for('homeAdmin'))

@app.route("/homeActivos")
@login_required
def homeActivos():
    # Verificar el rol del usuario
    if current_user.rol == "administrador":
        nombre_usuario = current_user.username
        # Obtener todos los eventos
        eventos, mensaje = ModelEvento.get_all_eventos_activos(db)

        if eventos is None:
            return render_template("adminUser/homeActivos.html", error=mensaje)

        return render_template("adminUser/homeActivos.html", eventos=eventos, nombre_usuario=nombre_usuario)
    else:
        # Si el usuario no es un administrador, redirigir a una página de error 404
        #abort(404)
        return render_template('error/404.html'), 404
    
@app.route("/homeCancelados")
@login_required
def homeCancelados():
    # Verificar el rol del usuario
    if current_user.rol == "administrador":
        nombre_usuario = current_user.username
        # Obtener todos los eventos
        eventos, mensaje = ModelEvento.get_all_eventos_cancelados(db)

        if eventos is None:
            return render_template("adminUser/homeCancelados.html", error=mensaje)

        return render_template("adminUser/homeCancelados.html", eventos=eventos, nombre_usuario=nombre_usuario)
    else:
        # Si el usuario no es un administrador, redirigir a una página de error 404
        #abort(404)
        return render_template('error/404.html'), 404

@app.route("/homeProximos")
@login_required
def homeProximos():
    # Verificar el rol del usuario
    if current_user.rol == "administrador":
        nombre_usuario = current_user.username
        # Obtener todos los eventos
        eventos, mensaje = ModelEvento.get_all_eventos_proximos(db)

        if eventos is None:
            return render_template("adminUser/homeProximos.html", error=mensaje)

        return render_template("adminUser/homeProximos.html", eventos=eventos, nombre_usuario=nombre_usuario)
    else:
        # Si el usuario no es un administrador, redirigir a una página de error 404
        #abort(404)
        return render_template('error/404.html'), 404
    
@app.route('/assistEventUsersList/<_id>', methods=['GET', 'POST'])
@login_required
def assistEventUsersList(_id):
    if current_user.rol == "administrador":
        nombre_usuario = current_user.username
        # Obtener la lista de usuarios que asistieron al evento
        usuarios_asistidos, evento_info = ModelEvento.get_list_users_by_asist_event(db, _id)

        if usuarios_asistidos is None:
            mensaje = "Error al obtener la lista de usuarios que asistieron al evento."
            return render_template("adminUser/eventUsersList.html", error=mensaje)

        return render_template('adminUser/eventUsersList.html', usuarios=usuarios_asistidos, nombre_usuario=nombre_usuario, evento=evento_info)
    else:
        return render_template('error/404.html'), 404



@app.route('/protected')
@login_required
def protected():
    return "<h1>This is a protected view, only for authenticated users.</h1>"

@app.route('/test')
def test():
    return render_template('error/404.html')


def status_401(error):
    return redirect(url_for('login'))

def status_403(error):
    return render_template('error/403.html'),403

@app.errorhandler(404)
def status_404(error):
    return render_template('error/404.html'),404

def status_500(error):
    return render_template('error/500.html'),500

def status_503(error):
    return render_template('error/503.html'),503


if __name__ == '__main__':
    app.config.from_object(config['development'])
    csrf.init_app(app)
    #app.register_error_handler(401, status_401)
    #app.register_error_handler(404, status_404)
    app.run(debug=False, host="0.0.0.0",port=os.getenv("PORT",default=5000))
