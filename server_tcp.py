"""Servidor TCP para chat multiusuario con mensajes privados y grupales,
se importa la libreria socket para crear el servidor y manejar las conexiones de red
y threading para atender a los clientes de manera simultanea

- import datetime para obtener la fecha y hora actual para los mensajes
- import hashlib para generar hashes SHA-256 de las contraseñas de los usuarios
- import socket para crear sockets de red
- import threading para manejar multiples clientes simultaneamente
- HOST y PORT definen la direccion y puerto donde el servidor escucha
"""
import datetime
import socket
import threading
import logging
import rsa
import hashlib

HOST = "0.0.0.0"
PORT = 5000


"""Genera un par de claves RSA para el servidor, esto se hace al inicio para que el servidor tenga su propia clave publica y privada
que se usara para cifrar mensajes privados enviados a los clientes, el proceso de generacion de claves puede tardar unos segundos, por eso 
se muestra un mensaje informando al usuario, una vez generadas se confirma que se han generado con exito"""
logging.info("Generando llaves RSA del servidor... (esto puede tardar unos segundos)")
SERVER_PUB_KEY, SERVER_PRIV_KEY = rsa.newkeys(2048)
logging.info("Llaves generadas con éxito.")


"""Set up del logging para registrar eventos importantes del servidor, 
como conexiones, desconexiones y errores, en un archivo de texto llamado 
'bitacora_servidor.log' y también imprimirlos en la consola."""
logging.basicConfig(
    level=logging.INFO, # Nivel mínimo a registrar. 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bitacora_servidor.log", encoding='utf-8'), # Escribe en el archivo
        logging.StreamHandler() # Imprime en la consola al mismo tiempo
    ]
)


"""se usa UN diccionario para almacenar los clientes conectados, donde la clave es el nombre de usuario
y el valor es el objeto de conexion del socket al que corresponde ese usuario PERMITIENDO enviar mensajes
a cualquier cliente usando solo su nombre.
threading.lock() funciona como un semaforo evitando problemas cuando varios hilos intentan acceder o modificar
el diccionario al mismo tiempo"""
clientes = {} # guardar {nombre: {"conn": conn, "pubkey": llave_publica}            
lock = threading.Lock()

"""usuarios_registrados guarda en memoria los usuarios que se han conectado al servidor donde la clave es el nombre
de usuario y el valor es el hash SHA-256 de su contraseña
"""
usuarios_registrados = {} # guardar {nombre: hash_sha256_contrasena}
 
 
def hash_sha256(texto):
    """Recibe una cadena de texto y devuelve su representacion en hash SHA-256 en formato hexadecimal
    esto se usa para guardar las contraseñas de forma segura sin almacenarlas en texto plano
    hashlib.sha256 genera el hash y .hexdigest() lo convierte a una cadena de caracteres hexadecimales"""
    return hashlib.sha256(texto.encode('utf-8')).hexdigest()


"""remitente contiene el nombre del usuario que envió el mensaje
Es opcional. Si es None, el mensaje se envía a todos, si tiene valor se excluye al remitente
"""
def enviar_con_longitud(conn, datos_bytes):
    """Envia datos precedidos de 4 bytes que indican su longitud.
    Esto evita que TCP fusione dos mensajes cifrados en un solo paquete,
    lo que causaria errores al descifrar con RSA."""
    import struct
    longitud = struct.pack('>I', len(datos_bytes))  # 4 bytes big-endian
    conn.sendall(longitud + datos_bytes)


def broadcast(mensaje, remitente=None):
    """Envia un mensaje a todos los clientes conectados, excepto al remitente si se especifica, 
    de forma que itera sobre el diccionario de clientes y envia el mensaje a cada uno
    se usa un bloque try-catch por si falla un envio, continua con el siguiente cliente
    """

    for nombre, datos_cliente in clientes.items(): 
        if nombre != remitente:
            try:
                mensaje_cifrado = rsa.encrypt(mensaje.encode('utf-8'), datos_cliente['pubkey']) #cifra el mensaje usando la clave publica del cliente destino
                enviar_con_longitud(datos_cliente['conn'], mensaje_cifrado)
            except Exception as e:
                logging.warning(f"Fallo al enviar mensaje a '{nombre}': {e}")


import struct

def _recibir_exacto(s, n):
    """Lee exactamente n bytes del socket."""
    datos = b""
    while len(datos) < n:
        p = s.recv(n - len(datos))
        if not p:
            return None
        datos += p
    return datos

def _recv_con_longitud(s):
    """Lee 4 bytes de longitud y luego el mensaje completo."""
    h = _recibir_exacto(s, 4)
    if h is None:
        return None
    return _recibir_exacto(s, struct.unpack(">I", h)[0])

def manejarCliente(conn, addr):
    """Maneja la comunicacion con un cliente conectado, registra el nombre de usuario,
    recibe mensajes y los procesa para mensajes privados o grupales, si el cliente se desconecta 
    elimina al cliente de la lista y avisa a los demas. Conn es el socket del cliente y addr es su direccion"""
    nombre = None #hasta que el cliente se registre no hay nombre
    try:
        
        # HandShake criptográfico para intercambio de claves
        conn.sendall(SERVER_PUB_KEY.save_pkcs1()) #envia la clave publica del servidor al cliente para que pueda cifrar mensajes privados para el servidor
        
        # Recibir llave pública del cliente
        client_pub_pem = conn.recv(2048) #recibe la clave publica del cliente en formato PEM
        client_pub_key = rsa.PublicKey.load_pkcs1(client_pub_pem) #carga la clave publica del cliente para usarla en el cifrado de mensajes privados enviados a ese cliente
 
        # Pedir el usuario, para enviar el prompt cifrado con la llave del cliente
        prompt_cifrado = rsa.encrypt(b"Usuario: ", client_pub_key) #cifra el prompt usando la clave publica del cliente para que solo el cliente pueda descifrarlo
        enviar_con_longitud(conn, prompt_cifrado) #envia el prompt cifrado al cliente para solicitar el nombre de usuario
 
        # Recibir el nombre de usuario (viene cifrado por el cliente) y descifrarlo
        nombre_cifrado = _recv_con_longitud(conn)
        # descifra el nombre usando la clave privada del servidor y lo decodifica a string, ademas se le quitan espacios en blanco al inicio y final por si el cliente los ingreso por error
        nombre = rsa.decrypt(nombre_cifrado, SERVER_PRIV_KEY).decode('utf-8').strip()
 
        # Pedir la contraseña, tambien cifrada con la llave publica del cliente para que solo el cliente pueda verla
        prompt_pass_cifrado = rsa.encrypt(b"Contrasena: ", client_pub_key) #cifra el prompt de contraseña con la llave publica del cliente
        enviar_con_longitud(conn, prompt_pass_cifrado) #envia el prompt de contraseña cifrado al cliente
 
        # Recibir la contraseña (viene cifrada por el cliente) y descifrarla
        pass_cifrado = _recv_con_longitud(conn)
        contrasena = rsa.decrypt(pass_cifrado, SERVER_PRIV_KEY).decode('utf-8').strip() #descifra la contraseña usando la clave privada del servidor
        contrasena_hash = hash_sha256(contrasena) #convierte la contraseña a su hash SHA-256 antes de guardarla o compararla, la contraseña en texto plano nunca se almacena
 
        with lock:
            """with lock bloquea el acceso para evitar conflictos entre los hilos, despues se verifica
            si el servidor esta lleno, si el nombre ya esta activo en este momento, y si el usuario ya estaba
            registrado se valida su contraseña con el hash guardado, en caso contrario se registra como nuevo"""
 
            if len(clientes) >= 5:
                conn.sendall(b"ERROR: Servidor lleno. Maximo 5 usuarios.\n")
                conn.close()
                return
 
            if nombre in clientes:
                # el usuario ya tiene una sesion activa en este momento, no se permite doble conexion
                error_msg = rsa.encrypt(b"ERROR: Usuario ya conectado\n", client_pub_key) #cifra el error con la llave del cliente
                enviar_con_longitud(conn, error_msg)
                logging.warning(f"Conexión rechazada desde {addr}: El nombre '{nombre}' ya está activo.")
                conn.close()
                return
 
            if nombre in usuarios_registrados:
                """el usuario ya existe en el diccionario de registrados, se valida que la contraseña
                ingresada coincida con el hash guardado comparando hash con hash, si no coinciden se rechaza"""
                if usuarios_registrados[nombre] != contrasena_hash: #compara el hash de la contraseña ingresada con el hash guardado
                    error_auth = rsa.encrypt(b"ERROR: Contrasena incorrecta\n", client_pub_key) #cifra el mensaje de error con la llave del cliente
                    enviar_con_longitud(conn, error_auth) #envia el error al cliente
                    logging.warning(f"Login fallido para '{nombre}' desde {addr}: contraseña incorrecta")
                    conn.close()
                    return
                # contraseña correcta, se autoriza el acceso al chat
                enviar_con_longitud(conn, rsa.encrypt(b"AUTH_OK\n", client_pub_key)) #notifica al cliente que la autenticacion fue exitosa
                logging.info(f"Usuario '{nombre}' autenticado correctamente desde {addr}")
            else:
                """el usuario es nuevo, se guarda su nombre y el hash SHA-256 de su contraseña en el diccionario
                usuarios_registrados para que en futuras conexiones se pueda validar su contraseña"""
                usuarios_registrados[nombre] = contrasena_hash #guarda el hash SHA-256, nunca la contraseña en texto plano
                enviar_con_longitud(conn, rsa.encrypt(b"AUTH_OK\n", client_pub_key)) #notifica al cliente que el registro fue exitoso
                logging.info(f"Usuario '{nombre}' registrado en memoria (hash SHA-256) desde {addr}")
 
            # Agregar cliente al diccionario de conexiones activas con su conexion y clave publica
            clientes[nombre] = {"conn": conn, "pubkey": client_pub_key}
 
            # Enviar al nuevo cliente la lista de usuarios ya conectados
            for user in clientes:
                if user != nombre:
                    try:
                        msg_sistema = f"SISTEMA_ADD:{user}\n"
                        msg_cifrado = rsa.encrypt(msg_sistema.encode('utf-8'), client_pub_key)
                        enviar_con_longitud(conn, msg_cifrado)
                    except:
                        pass
                    
        # Registramos la conexión exitosa del nuevo usuario
        logging.info(f"Usuario '{nombre}' conectado desde {addr}") 
 
        """Muestra el servidor de quien se conecto y avisa a todos los clientes que alguien nuevo entro"""
        print(f"[TCP] {nombre} conectado desde {addr}")
 
        # Avisar a los demas que este usuario se conectó (evento de sistema)
        broadcast(f"SISTEMA_ADD:{nombre}\n", remitente=nombre)
        broadcast(f"*** {nombre} se unio al chat ***\n")
 
        while True:
            """Bucle principal para recibir mensajes del cliente, espera mensajes del cliente y si
            el mensaje esta vacio significa que se desconecto, si hay algun error al recibir, se sale del ciclo"""
            msg_cifrado = _recv_con_longitud(conn)
            if not msg_cifrado:
                break
 
            # Descifrar el mensaje usando la clave privada del servidor y decodificarlo a string, ademas se le quitan espacios en blanco al inicio y final por si el cliente los ingreso por error
            msg = rsa.decrypt(msg_cifrado, SERVER_PRIV_KEY).decode('utf-8').strip()
 
            """identifica el comando del mensaje que es privado, despues separa el destinatario y el mensaje
            y por ultimo reconstruye el mensaje completo. Se verifica si el destino existe, envia el mensaje, 
            envia la confirmacion al remitente y despues salta al sig mensaje con continue"""
            
            fecha = datetime.datetime.now().strftime("%d/%m/%Y %I:%M:%S %p")
            if msg.startswith("/priv"):
                _, destino, *contenido = msg.split()
                contenido = " ".join(contenido)
 
                if destino in clientes:
                    destino_pubkey = clientes[destino]['pubkey'] #obtiene la clave publica del cliente destino para cifrar el mensaje privado
                    msg_para_destino = f"[{fecha}] [PRIVADO de {nombre}] {contenido}\n" #mensaje que recibira el cliente destino, incluye la fecha, el nombre del remitente y el mensaje
                    enviar_con_longitud(clientes[destino]['conn'], rsa.encrypt(msg_para_destino.encode('utf-8'), destino_pubkey)) #envia el mensaje cifrado al cliente destino usando su clave publica para que solo el cliente destino pueda descifrarlo
                    
                    msg_para_remitente = f"[PRIVADO para {destino}] [Fecha:{fecha}] {contenido}\n" 
                    enviar_con_longitud(conn, rsa.encrypt(msg_para_remitente.encode('utf-8'), client_pub_key)) #envia la confirmacion al remitente cifrada con su clave publica para que solo el remitente pueda descifrarla
                    
                    logging.info(f"Mensaje privado de '{nombre}' a '{destino}': ***Cifrado***") #registramos el evento del mensaje privado sin guardar el contenido por seguridad
                else:
                    err = rsa.encrypt(b"ERROR: Usuario no encontrado\n", client_pub_key) #cifra el mensaje de error usando la clave publica del remitente para que solo el remitente pueda descifrarlo
                    enviar_con_longitud(conn, err) #envia el mensaje de error al remitente
                    logging.warning(f"Intento de mensaje privado a '{destino}' fallido desde '{nombre}': Usuario no encontrado") #registramos el intento fallido de mensaje privado por usuario no encontrado
                continue
 
            """envia mensajes grupales a todos los clientes conectados con la fecha/hora actual"""    
            broadcast(f"[{nombre}] [Fecha:{fecha}] {msg}\n", remitente=nombre)
 
    except Exception as e:
        if nombre:
            logging.error(f"Error en la conexión con el cliente '{nombre}': {e}")
        else:
            logging.error(f"Error en la conexión con {addr}: {e}")
   
    finally:
        # Eliminar cliente y notificar a los demas
        with lock: #bloquea el acceso al diccionario para evitar conflictos
            if nombre in clientes:
                del clientes[nombre] #elimina al cliente del diccionario
 
        # Notificar evento de sistema y mensaje legible
        if nombre:
            broadcast(f"SISTEMA_DEL:{nombre}\n")
            broadcast(f"*** {nombre} salio del chat ***\n")
            # Log de desconexión
            logging.info(f"Usuario '{nombre}' desconectado")
        conn.close()
 
"""este metodo esta declarado al final ya que primero se definen las funciones que maneja el servidor por si pasa algun error asegurandonos que 
todas las funciones esten definidas antes de usarlas
"""
def main():
    """Configura e inicia el servidor creando un socket TCP despues lo asocia al puerto y 
    pone al servidor en modo escucha
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) #permite reutilizar el puerto inmediatamente despues de cerrar el servidor sin esperar el tiempo de espera del sistema operativo
    server.bind((HOST, PORT))
    server.listen()
    
    server.settimeout(1) #establece un tiempo de espera para aceptar conexiones permitiendo manejar interrupciones para que el servidor pueda cerrarse limpiamente 
 
    # Log de inicio del servidor
    logging.info(f"Servidor TCP iniciado y escuchando en {HOST}:{PORT}")
 
    try:
        while True:
            try:
                conn, addr = server.accept() #acepta una nueva conexion entrante
                threading.Thread(target=manejarCliente, args=(conn, addr), daemon=True).start() #target es la funcion que maneja al cliente, 
                #args son los argumentos que recibe la funcion y daemon=True permite que los hilos se cierren automaticamente al cerrar el programa principal
 
            except socket.timeout: #si no hay conexiones en el tiempo de espera, continua el bucle
                pass  
 
    except KeyboardInterrupt: #captura la interrupcion del teclado (Ctrl+C) para cerrar el servidor limpiamente
       logging.info("Interrupción por teclado detectada. Deteniendo servidor...")
    finally:
        """"Cierra el socket del servidor al terminar"""
        server.close()
        logging.info("Servidor cerrado de forma segura.")
 
 
if __name__ == "__main__":
    main()