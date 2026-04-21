# LA DOCUMENTACIÓN DEL ARCHIVO SE CAMBIO A # PARA QUE NO INTERFIERA CON STREAMLIT, YA QUE APARECIA EN LA INTERFAZ WEB

 
#  se crea una aplicacion web usando streamlit para el chat TCP/UDP con una interfaz grafica de usuario (GUI)
# que permite a los usuarios conectarse a un servidor de chat usando TCP o UDP, enviar y recibir
# mensajes, y ver el historial de chat en tiempo real.
import streamlit as st
import time
import threading
import datetime
from cliente_tcp import ClienteTCP
from cliente_udp import ClienteUDP


# CONFIGURACIÓN VISUAL DE LA APLICACIÓN WEB
st.set_page_config(
    page_title="Chat TCP/UDP", 
    page_icon="💬",
    layout="wide"
)

# Se inicializan las variables de sesion necesarias para mantener el estado de la aplicacion web,
# como el objeto cliente, el historial de mensajes, el estado de conexion, el tipo de conexion
# y el nombre de usuario

# INICIALIZACIÓN DE VARIABLES DE SESIÓN 

# estas variables provienen de las clases ClienteTCP y ClienteUDP:

# st.session_state.cliente_obj guarda el objeto cliente (TCP o UDP) para usarlo en otras partes de la aplicacion
# st.session_state.historial es una lista que almacena los mensajes recibidos para mostrarlos en la interfaz
# st.session_state.conectado indica si el usuario esta conectado al servidor
# st.session_state.tipo_conexion guarda el tipo de conexion (TCP o UDP) para mostrarlo en la interfaz
# st.session_state.nombre_usuario guarda el nombre de usuario ingresado por el usuario
# st.session_state.usuarios es una lista que almacena los nombres de los usuarios conectados


if 'cliente_obj' not in st.session_state:
    st.session_state.cliente_obj = None
if 'historial' not in st.session_state:
    st.session_state.historial = []
if 'conectado' not in st.session_state:
    st.session_state.conectado = False
if 'tipo_conexion' not in st.session_state:
    st.session_state.tipo_conexion = ""
if 'nombre_usuario' not in st.session_state:
    st.session_state.nombre_usuario = ""
if 'usuarios' not in st.session_state:
    # lista mutable compartida con el hilo de escucha 
    st.session_state.usuarios = [] #es una lista para mantener los usuarios conectados

# Hilo escucha funciona en segundo plano para recibir mensajes del servidor y actualizar
# el historial de mensajes en la interfaz de usuario. Se modificó para no usar
# st.session_state directamente dentro del hilo, ya que esto puede causar errores de
# contexto en Streamlit. Recibimos las referencias como argumentos explícitos.
def hilo_escucha(cliente_instancia, lista_mensajes_referencia, lista_usuarios_referencia):
    """
    Escucha mensajes entrantes. 
    NO usa st.session_state directamente para evitar errores de contexto.
    Este bloque detecta cuando un usuario *entra* o *sale* del chat. El servidor a veces manda mensajes como:*** usuario se unio al chat ***
    La idea es:
    1. Revisar si el mensaje contiene "se unio al chat" o "salio del chat"
    2. Separar el mensaje usando "***" para obtener el nombre del usuario
    3. Agregarlo a la lista de usuarios si se unió, o quitarlo de la lista si salió
    """
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

# Este bloque crea la barra lateral de la aplicacion web donde los usuarios pueden conectarse
# o desconectarse del servidor, y seleccionar el protocolo (TCP o UDP). Tambien muestra el
# estado de conexion actual y permite ingresar el nombre de usuario.
# - st.sidebar es para crear una barra lateral en la aplicacion web
# - st.session_state se usa para mantener el estado de la aplicacion entre interacciones del usuario
# - st.session_state.cliente_obj = cliente guarda el objeto cliente (TCP o UDP) para usarlo en otras partes de la aplicacion
# - st.session_state.conectado indica si el usuario esta conectado al servidor
# - st.session_state.tipo_conexion guarda el tipo de conexion (TCP o UDP) para mostrarlo en la interfaz
# - st.session_state.nombre_usuario guarda el nombre de usuario ingresado por el usuario
# - iniciarHiloEscucha es un hilo que ejecuta la funcion hilo_escucha en segundo plano para recibir mensajes del servidor sin bloquear la interfaz de usuario
# - st.rerun() se usa para refrescar la interfaz de usuario despues de conectarse o desconectarse
# - time.sleep(0.5) da un pequeño retraso para asegurar que el hilo de escucha se inicie antes de refrescar la interfaz
# - st.message, st.success, st.error, st.warning, st.info son funciones de Streamlit para mostrar mensajes al usuario en diferentes estilos

with st.sidebar:
    st.header("🔌 Conexión")
    
    if not st.session_state.conectado:
        nombre_input = st.text_input("Nombre de Usuario", placeholder="Ej: Maria")
        protocolo = st.selectbox("Protocolo", ["TCP", "UDP"])
        #Botón de conectar
        if st.button("Conectar", type="primary"):
            if nombre_input:
                st.session_state.nombre_usuario = nombre_input
                
                # Instanciamos la clase correcta
                if protocolo == "TCP":
                    cliente = ClienteTCP()
                    st.session_state.tipo_conexion = "TCP"
                else:
                    cliente = ClienteUDP()
                    st.session_state.tipo_conexion = "UDP"

                # Conectamos
                exito, info = cliente.conectar(nombre_input)
                
                if exito:
                    st.session_state.cliente_obj = cliente
                    st.session_state.conectado = True
                    st.success(info)
                    
                    # Iniciamos el hilo de escucha
                    # Pasamos los objetos EXPLICITAMENTE al hilo.
                    # Así el hilo no tiene que buscar 'st.session_state'
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
                st.warning("El nombre es obligatorio.")
                
        st.info("Asegúrate de correr `servidores.py` primero.")
        
    else:
        st.success(f"🟢 En línea como **{st.session_state.nombre_usuario}**")
        st.write(f"Protocolo: **{st.session_state.tipo_conexion}**")
        
        st.markdown("---")
        st.caption("Comandos especiales:")
        st.code("/priv usuario mensaje")
        st.markdown("---")
        
        if st.button("Desconectar", type="primary"):
            if st.session_state.cliente_obj:
                st.session_state.cliente_obj.cerrar()
            st.session_state.conectado = False
            st.session_state.cliente_obj = None
            st.session_state.historial = []
            st.rerun()

# Área principal de la aplicacion web que muestra el titulo del chat, el historial de mensajes
# y un campo de entrada para enviar nuevos mensajes
# - st.title muestra el titulo principal de la aplicacion
# - col_msg, col_users = st.columns([3, 1]) crea dos columnas, una para los mensajes y otra para la lista de usuarios conectados
# - contenedor_mensajes = st.container(height=500) crea un contenedor para mostrar los mensajes con una altura fija
# - st.chat_input crea un campo de entrada para que el usuario escriba mensajes
st.title(f"Sala de Chat {st.session_state.tipo_conexion}")

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
    prompt = st.chat_input(f"Escribe un mensaje como {st.session_state.nombre_usuario}...")
    
    if prompt:
        # Enviar al servidor
        st.session_state.cliente_obj.enviar_mensaje(prompt)
        
        # ECO LOCAL para el historial
        hora_actual = datetime.datetime.now().strftime("%H:%M:%S")
        mi_mensaje_formateado = f"[Yo] [{hora_actual}] {prompt}"
        st.session_state.historial.append(mi_mensaje_formateado)
        
        st.rerun()

    
    # Esto mantiene la UI actualizada con lo que el hilo recibe
    time.sleep(1)
    st.rerun()

else:
    st.write("👈 Por favor, inicia sesión en el menú de la izquierda.")