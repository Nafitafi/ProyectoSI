# LA DOCUMENTACIÓN DEL ARCHIVO SE CAMBIO A # PARA QUE NO INTERFIERA CON STREAMLIT, YA QUE APARECIA EN LA INTERFAZ WEB

# se crea una aplicacion web usando streamlit para el chat TCP con una interfaz grafica de usuario (GUI)
# que permite a los usuarios conectarse a un servidor de chat usando TCP, enviar y recibir
# mensajes, y ver el historial de chat en tiempo real.
# Se incluye un timer de inactividad: si pasan 5 minutos sin enviar mensajes se pregunta al usuario
# si desea seguir en el chat, esa ventana de dialogo dura maximo 15 segundos y si no responde se cierra la sesion
import streamlit as st
import time
import threading
import datetime
import re
from cliente_tcp import ClienteTCP

# Reglas de validacion 
NOMBRE_MIN = 3
NOMBRE_MAX = 20
PASS_MIN   = 4
PASS_MAX   = 50
NOMBRE_REGEX = re.compile(r'^[a-zA-Z0-9_\-]+$')

def validar_nombre(nombre):
    #Valida longitud y caracteres permitidos del nombre de usuario.
    #Devuelve (True, None) si es valido o (False, mensaje_error) si no lo es
    if not nombre:
        return False, "El nombre de usuario no puede estar vacio"
    if len(nombre) < NOMBRE_MIN:
        return False, f"El nombre debe tener al menos {NOMBRE_MIN} caracteres"
    if len(nombre) > NOMBRE_MAX:
        return False, f"El nombre no puede superar {NOMBRE_MAX} caracteres"
    if not NOMBRE_REGEX.match(nombre):
        return False, "El nombre solo puede contener letras, numeros, _ y -"
    return True, None

def validar_contrasena(contrasena):
    #Valida longitud de la contrasena.
    #Devuelve (True, None) si es valida o (False, mensaje_error) si no lo es
    if not contrasena:
        return False, "La contrasena no puede estar vacia"
    if len(contrasena) < PASS_MIN:
        return False, f"La contrasena debe tener al menos {PASS_MIN} caracteres"
    if len(contrasena) > PASS_MAX:
        return False, f"La contrasena no puede superar {PASS_MAX} caracteres"
    return True, None


# CONFIGURACIÓN VISUAL DE LA APLICACIÓN WEB
st.set_page_config(
    page_title="Chat TCP", 
    page_icon="💬",
    layout="wide"
)

# LIMPIEZA DE ESTADO AL RECARGAR LA PÁGINA
# Cuando el usuario recarga la pagina, Streamlit destruye el st.session_state pero el socket
# del servidor puede quedar abierto con el nombre del usuario todavia registrado. Para evitar
# que al intentar reconectarse aparezca "Usuario ya conectado", se detecta si habia una sesion
# activa (conectado=True) pero ya no hay objeto cliente valido (cliente_obj=None), lo que indica
# una recarga abrupta, y se fuerza el reseteo completo de todas las variables de sesion.
# Nota: el servidor por su parte detecta el socket muerto y lo limpia automaticamente tambien.
if st.session_state.get('conectado', False) and st.session_state.get('cliente_obj') is None:
    # habia una sesion marcada como activa pero sin objeto cliente, es una recarga de pagina
    for key in ['conectado', 'cliente_obj', 'historial', 'usuarios',
                'nombre_usuario', 'ultimo_mensaje_ts', 'timer_dialogo_activo', 'dialogo_mostrado_ts']:
        if key in st.session_state:
            del st.session_state[key] #elimina la clave para que se reinicialice con su valor por defecto abajo

# Se inicializan las variables de sesion necesarias para mantener el estado de la aplicacion web,
# como el objeto cliente, el historial de mensajes, el estado de conexion y el nombre de usuario

# INICIALIZACIÓN DE VARIABLES DE SESIÓN 

# estas variables provienen de la clase ClienteTCP:

# st.session_state.cliente_obj guarda el objeto cliente TCP para usarlo en otras partes de la aplicacion
# st.session_state.historial es una lista que almacena los mensajes recibidos para mostrarlos en la interfaz
# st.session_state.conectado indica si el usuario esta conectado al servidor
# st.session_state.nombre_usuario guarda el nombre de usuario ingresado por el usuario
# st.session_state.usuarios es una lista que almacena los nombres de los usuarios conectados
# st.session_state.ultimo_mensaje_ts guarda la marca de tiempo del ultimo mensaje enviado para el timer de inactividad
# st.session_state.timer_dialogo_activo indica si el dialogo de inactividad esta visible en pantalla
# st.session_state.dialogo_mostrado_ts guarda la marca de tiempo de cuando aparecio el dialogo para calcular el countdown de 15 segundos

if 'cliente_obj' not in st.session_state:
    st.session_state.cliente_obj = None
if 'historial' not in st.session_state:
    st.session_state.historial = []
if 'conectado' not in st.session_state:
    st.session_state.conectado = False
if 'nombre_usuario' not in st.session_state:
    st.session_state.nombre_usuario = ""
if 'usuarios' not in st.session_state:
    # lista mutable compartida con el hilo de escucha 
    st.session_state.usuarios = [] #es una lista para mantener los usuarios conectados
if 'ultimo_mensaje_ts' not in st.session_state:
    st.session_state.ultimo_mensaje_ts = None #marca de tiempo del ultimo mensaje enviado por el usuario
if 'timer_dialogo_activo' not in st.session_state:
    st.session_state.timer_dialogo_activo = False #True cuando el dialogo de inactividad esta visible
if 'dialogo_mostrado_ts' not in st.session_state:
    st.session_state.dialogo_mostrado_ts = None #marca de tiempo de cuando se mostro el dialogo por primera vez


# Hilo escucha funciona en segundo plano para recibir mensajes del servidor y actualizar
# el historial de mensajes en la interfaz de usuario. Se modificó para no usar
# st.session_state directamente dentro del hilo, ya que esto puede causar errores de
# contexto en Streamlit. Recibimos las referencias como argumentos explícitos.
def hilo_escucha(cliente_instancia, lista_mensajes_referencia, lista_usuarios_referencia):
  
    # Usamos la propiedad .conectado del objeto cliente
    while cliente_instancia.conectado:
        try:
            # Bloqueante hasta recibir algo
            mensaje = cliente_instancia.recibir_mensaje()

            if mensaje:
                print(f"[DEBUG Hilo] Recibido: {mensaje}")

                # Detectar mensajes del sistema que gestionan usuarios
                if mensaje.startswith("SISTEMA_ADD:"):
                    user = mensaje.replace("SISTEMA_ADD:", "").strip()
                    if user and user not in lista_usuarios_referencia:
                        lista_usuarios_referencia.append(user)
                elif mensaje.startswith("SISTEMA_DEL:"):
                    user = mensaje.replace("SISTEMA_DEL:", "").strip()
                    if user and user in lista_usuarios_referencia:
                        try:
                            lista_usuarios_referencia.remove(user)
                        except ValueError:
                            pass

                else:
                    # algunos servidores pueden enviar líneas tipo "*** usuario se unio al chat ***"
                    if "se unio al chat" in mensaje and "***" in mensaje:
                        parts = mensaje.split("***")
                        if len(parts) >= 2:
                            candidate = parts[1].strip()
                            # candidate puede ser "usuario se unio al chat" 
                            user = candidate.split()[0]
                            if user and user not in lista_usuarios_referencia:
                                #si el usuario no está en la lista, lo agregamos
                                lista_usuarios_referencia.append(user)
                    elif "salio del chat" in mensaje and "***" in mensaje:
                        parts = mensaje.split("***")
                        
                        if len(parts) >= 2:
                            candidate = parts[1].strip()
                            user = candidate.split()[0]
                            if user and user in lista_usuarios_referencia:
                                try:
                                    lista_usuarios_referencia.remove(user)
                                except ValueError:
                                    pass

                    # Al ser una lista mutable, podemos hacer append y Streamlit lo verá
                    lista_mensajes_referencia.append(mensaje)
            else:
                # Si retorna None, el servidor cerró o hubo error
                break
        except Exception as e:
            print(f"[ERROR Hilo]: {e}")
            break
        
        time.sleep(0.1)


def desconectar():
    
    if st.session_state.cliente_obj:
        st.session_state.cliente_obj.cerrar() #cierra el socket del cliente TCP
    st.session_state.conectado = False
    st.session_state.cliente_obj = None
    st.session_state.historial = []
    st.session_state.usuarios = []
    st.session_state.ultimo_mensaje_ts = None #reinicia la marca de tiempo del timer
    st.session_state.timer_dialogo_activo = False #oculta el dialogo si estaba visible
    st.session_state.dialogo_mostrado_ts = None #reinicia el countdown del dialogo


# Este bloque crea la barra lateral de la aplicacion web donde los usuarios pueden conectarse
# o desconectarse del servidor. Tambien muestra el estado de conexion actual y permite ingresar 
# el nombre de usuario y la contraseña. La contraseña se envia cifrada al servidor y se guarda
# como hash SHA-256 en memoria, nunca en texto plano.
# - st.sidebar es para crear una barra lateral en la aplicacion web
# - st.session_state se usa para mantener el estado de la aplicacion entre interacciones del usuario
# - st.session_state.cliente_obj = cliente guarda el objeto cliente TCP para usarlo en otras partes de la aplicacion
# - st.session_state.conectado indica si el usuario esta conectado al servidor
# - st.session_state.nombre_usuario guarda el nombre de usuario ingresado por el usuario
# - iniciarHiloEscucha es un hilo que ejecuta la funcion hilo_escucha en segundo plano para recibir mensajes del servidor sin bloquear la interfaz de usuario
# - st.rerun() se usa para refrescar la interfaz de usuario despues de conectarse o desconectarse
# - time.sleep(0.5) da un pequeño retraso para asegurar que el hilo de escucha se inicie antes de refrescar la interfaz
# - st.message, st.success, st.error, st.warning, st.info son funciones de Streamlit para mostrar mensajes al usuario en diferentes estilos

with st.sidebar:
    st.header("🔌 Conexión")
    
    if not st.session_state.conectado:
        nombre_input = st.text_input("Nombre de Usuario", placeholder="Ej: Maria")
        contrasena_input = st.text_input(
            "Contraseña",
            type="password", #oculta la contraseña mientras el usuario la escribe
            placeholder="Tu contraseña",
            help="Si es tu primera vez, se registrará con esta contraseña." #tooltip informativo
        )
        #Botón de conectar
        if st.button("Conectar", type="primary"):
            if nombre_input and contrasena_input: #verifica que ambos campos esten llenos antes de intentar conectar
                # Validar campos antes de intentar conectar al servidor
                nombre_ok, nombre_err = validar_nombre(nombre_input)
                pass_ok, pass_err = validar_contrasena(contrasena_input)

                if not nombre_ok:
                    st.error(f"Nombre invalido: {nombre_err}")
                elif not pass_ok:
                    st.error(f"Contrasena invalida: {pass_err}")
                else:
                    st.session_state.nombre_usuario = nombre_input

                    # Instanciamos el cliente TCP solo si los datos son validos
                    cliente = ClienteTCP()

                    # Conectamos pasando nombre y contrasena
                    exito, info = cliente.conectar(nombre_input, contrasena_input)
                
                    if exito:
                        st.session_state.cliente_obj = cliente
                        st.session_state.conectado = True
                        st.session_state.ultimo_mensaje_ts = time.time() #inicia el timer de inactividad desde el momento de la conexion
                        st.success(info)

                        # Iniciamos el hilo de escucha
                        # Pasamos los objetos EXPLICITAMENTE al hilo.
                        iniciarHiloEscucha = threading.Thread(
                            target=hilo_escucha,
                            args=(
                                st.session_state.cliente_obj,
                                st.session_state.historial,
                                st.session_state.usuarios,
                            ),
                            daemon=True,
                        )
                        iniciarHiloEscucha.start()

                        time.sleep(0.5)
                        st.rerun()
                    else:
                        st.error(f"Error: {info}")
            else:
                st.warning("El nombre y la contrasena son obligatorios.")
                
        st.info("Asegúrate de iniciar el servidor primero.")
        
    else:
        st.success(f"🟢 En línea como **{st.session_state.nombre_usuario}**")
        st.write(f"Protocolo: **TCP**")
        
        st.markdown("---")
        st.caption("Comandos especiales:")
        st.code("/priv usuario mensaje")
        st.markdown("---")
        
        if st.button("Desconectar", type="primary"):
            desconectar() #llama a la funcion de desconexion limpia
            st.rerun()

# Área principal de la aplicacion web que muestra el titulo del chat, el historial de mensajes
# y un campo de entrada para enviar nuevos mensajes
# - st.title muestra el titulo principal de la aplicacion
# - col_msg, col_users = st.columns([3, 1]) crea dos columnas, una para los mensajes y otra para la lista de usuarios conectados
# - contenedor_mensajes = st.container(height=500) crea un contenedor para mostrar los mensajes con una altura fija
# - st.chat_input crea un campo de entrada para que el usuario escriba mensajes
st.title(f"Sala de Chat TCP - Usuario: {st.session_state.nombre_usuario if st.session_state.conectado else 'No conectado'}")


# TIMER DE INACTIVIDAD
# Si el usuario no envía mensajes en 5 minutos (INACTIVIDAD_SEGUNDOS) se muestra un dialogo
# preguntando si desea seguir en el chat. El dialogo tiene un countdown de 15 segundos
# (DIALOGO_SEGUNDOS) y si el tiempo se agota la sesion se cierra automaticamente.
# Si el usuario responde "Si" se reinicia el timer. Si responde "No" se cierra la sesion.
INACTIVIDAD_SEGUNDOS = 1 * 60  # minuto expresado en segundos
DIALOGO_SEGUNDOS = 15           # segundos que el dialogo permanece activo antes de cerrar sesion

if st.session_state.conectado:
    ahora = time.time() #obtiene el tiempo actual en segundos para compararlo con las marcas de tiempo guardadas

    if st.session_state.timer_dialogo_activo:
        tiempo_transcurrido_dialogo = ahora - st.session_state.dialogo_mostrado_ts #segundos desde que aparecio el dialogo
        segundos_restantes = max(0, int(DIALOGO_SEGUNDOS - tiempo_transcurrido_dialogo)) #tiempo restante sin valores negativos

        if segundos_restantes == 0:
            # el tiempo se agoto, se cierra la sesion automaticamente sin esperar respuesta del usuario
            st.warning("⏰ Tiempo agotado. Cerrando sesión automáticamente...")
            time.sleep(1.5) #pausa breve para que el usuario pueda ver el mensaje antes de que desaparezca
            desconectar()
            st.rerun()
        else:
            # muestra el dialogo con el countdown de segundos restantes
            st.markdown("---")
            with st.container():
                st.warning(
                    f"🕐 ¿Quieres seguir en el chat?\n\n"
                    f"Esta ventana se cerrará automáticamente en **{segundos_restantes}** segundo(s).",
                    icon="⚠️"
                )
                col_si, col_no, _ = st.columns([1, 1, 4]) #columnas para los botones, la tercera es espacio vacio
                with col_si:
                    if st.button("✅ Sí", key="btn_si_timer", type="primary"):
                        # el usuario quiere seguir, se reinicia el timer de inactividad
                        st.session_state.timer_dialogo_activo = False #oculta el dialogo
                        st.session_state.dialogo_mostrado_ts = None #limpia la marca de tiempo del dialogo
                        st.session_state.ultimo_mensaje_ts = time.time() #reinicia el timer de inactividad desde ahora
                        st.rerun()
                with col_no:
                    if st.button("❌ No", key="btn_no_timer"):
                        # el usuario no quiere seguir, se cierra la sesion inmediatamente
                        desconectar()
                        st.rerun()
            st.markdown("---")

    else:
        
        if st.session_state.ultimo_mensaje_ts is not None:
            tiempo_inactivo = ahora - st.session_state.ultimo_mensaje_ts #segundos transcurridos desde el ultimo mensaje
            if tiempo_inactivo >= INACTIVIDAD_SEGUNDOS:
                # ya paso el tiempo de inactividad, se activa el dialogo de confirmacion
                st.session_state.timer_dialogo_activo = True #activa el dialogo
                st.session_state.dialogo_mostrado_ts = time.time() #guarda el momento en que aparecio el dialogo para el countdown
                st.rerun()


# Mostrar mensajes y lista de usuarios conectados en dos columnas
col_msg, col_users = st.columns([3, 1])

with col_msg:
    contenedor_mensajes = st.container(height=500)

    with contenedor_mensajes:
        if len(st.session_state.historial) == 0:
            st.info("Esperando mensajes... ¡Saluda!")

        for msj in st.session_state.historial:
            if "[PRIVADO" in msj:
                st.warning(msj, icon="🔒")
            elif "[Yo]" in msj:
                st.markdown(f"**{msj}**")
            elif "***" in msj:
                st.caption(msj)
            elif "[ERROR]" in msj:
                st.error(msj)
            else:
                st.text(msj)

with col_users:
    st.subheader("Usuarios conectados")
    if len(st.session_state.usuarios) == 0:
        st.write("(ninguno)")
    else:
        for u in st.session_state.usuarios:
            st.write(f"- {u}")

# Área de entrada de mensajes. Permite enviar mensajes al servidor y muestra el historial actualizado
# - prompt = st.chat_input crea un campo de entrada para que el usuario escriba mensajes
# - if st.session_state.conectado verifica que el usuario este conectado antes de permitir enviar mensajes
# - st.session_state.cliente_obj.enviar_mensaje(prompt) envia el mensaje al servidor usando el objeto cliente
# - st.session_state.historial.append(mi_mensaje_formateado) agrega el mensaje enviado al historial para mostrarlo en la interfaz
# - time.sleep(1) da un pequeño retraso para evitar sobrecargar la interfaz al refrescar
# - st.rerun() refresca la interfaz para mostrar los nuevos mensajes recibidos

if st.session_state.conectado:
    # no se muestra el campo de entrada si el dialogo de inactividad esta activo para evitar confusion
    if not st.session_state.timer_dialogo_activo:
        prompt = st.chat_input(f"Escribe un mensaje como {st.session_state.nombre_usuario}...")
        
        if prompt:
            # Enviar al servidor
            st.session_state.cliente_obj.enviar_mensaje(prompt)
            
            # ECO LOCAL para el historial
            hora_actual = datetime.datetime.now().strftime("%H:%M:%S")
            mi_mensaje_formateado = f"[Yo] [{hora_actual}] {prompt}"
            st.session_state.historial.append(mi_mensaje_formateado)
            
            # Reiniciar el timer de inactividad con cada mensaje enviado por el usuario
            st.session_state.ultimo_mensaje_ts = time.time() #actualiza la marca de tiempo al momento actual
            
            st.rerun()

    # Esto mantiene la UI actualizada con lo que el hilo recibe y tambien actualiza el countdown del dialogo
    time.sleep(1)
    st.rerun()

else:
    st.write("👈 Por favor, inicia sesión en el menú de la izquierda.")