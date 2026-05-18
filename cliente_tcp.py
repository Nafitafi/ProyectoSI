"""Cliente TCP con cifrado RSA y autenticacion por contraseña.
El servidor guarda la contraseña como hash SHA-256 en memoria, el cliente
la envia cifrada con RSA de modo que nunca viaja en texto plano por la red.

- import socket para crear el socket TCP de conexion al servidor
- import threading para escuchar mensajes del servidor en un hilo separado
- import rsa para el cifrado asimetrico de mensajes y contraseña
"""
import socket
import threading
import rsa
import struct
import re

SERVER_IP = "127.0.0.1"
SERVER_PORT = 5000

# Reglas de validación (deben coincidir con las del servidor)
NOMBRE_MIN = 3
NOMBRE_MAX = 20
PASS_MIN   = 4
PASS_MAX   = 50
NOMBRE_REGEX = re.compile(r'^[a-zA-Z0-9_\-]+$')

def validar_nombre(nombre):
    """Valida longitud y caracteres permitidos del nombre de usuario."""
    if not nombre:
        return False, "El nombre de usuario no puede estar vacío"
    if len(nombre) < NOMBRE_MIN:
        return False, f"El nombre debe tener al menos {NOMBRE_MIN} caracteres"
    if len(nombre) > NOMBRE_MAX:
        return False, f"El nombre no puede superar {NOMBRE_MAX} caracteres"
    if not NOMBRE_REGEX.match(nombre):
        return False, "El nombre solo puede contener letras, números, _ y -"
    return True, None

def validar_contrasena(contrasena):
    """Valida longitud de la contraseña."""
    if not contrasena:
        return False, "La contraseña no puede estar vacía"
    if len(contrasena) < PASS_MIN:
        return False, f"La contraseña debe tener al menos {PASS_MIN} caracteres"
    if len(contrasena) > PASS_MAX:
        return False, f"La contraseña no puede superar {PASS_MAX} caracteres"
    return True, None

def recibir_exacto(sock, n):
    """Lee exactamente n bytes del socket, bloqueante."""
    datos = b""
    while len(datos) < n:
        paquete = sock.recv(n - len(datos))
        if not paquete:
            return None
        datos += paquete
    return datos

def recibir_con_longitud(sock):
    """Lee 4 bytes de longitud y luego el mensaje completo.
    Evita el problema de TCP que fusiona mensajes consecutivos."""
    header = recibir_exacto(sock, 4)
    if header is None:
        return None
    longitud = struct.unpack('>I', header)[0]
    return recibir_exacto(sock, longitud)

def enviar_con_longitud(sock, datos_bytes):
    """Envía datos precedidos de 4 bytes de longitud."""
    longitud = struct.pack('>I', len(datos_bytes))
    sock.sendall(longitud + datos_bytes)

"""Clase ClienteTCP maneja la conexion TCP con el servidor, envio y recepcion de mensajes. se trata como objeto ya que
permite manejar mejor la conexion y sus estados, asi hay un solo socket por cliente y se puede reutilizar el objeto para
diferentes operaciones como conectar, enviar, recibir y cerrar la conexion
asi no se crean multiples sockets innecesarios, no hay errores de confusion entre sockets y se mantiene el estado de la conexion
"""
class ClienteTCP: #Clase para manejar la conexion TCP con el servidor
    def __init__(self): #Inicializa el socket TCP
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        self.conectado = False #False hasta que se conecte
        
        self.pubkey, self.privkey = rsa.newkeys(2048) #genera un par de claves RSA para este cliente, la clave publica se envia al servidor para que pueda cifrar mensajes privados para este cliente, y la clave privada se usa para descifrar mensajes privados recibidos del servidor
        self.server_pubkey = None #la clave publica del servidor se recibira al conectar y se guardara aqui para cifrar mensajes privados que se envien al servidor

    def conectar(self, nombre_usuario, contrasena):
        """Conecta al socket y realiza el handshake inicial de nombre y contraseña.
        Devuelve (True, mensaje) si fue exitoso o (False, error) si fallo.
        Usa protocolo longitud+datos para que TCP no fusione mensajes consecutivos."""
        try:
            self.sock.connect((SERVER_IP, SERVER_PORT))
            
            # Recibir llave pública del servidor (sin protocolo de longitud, es el primer envío)
            server_pub_pem = self.sock.recv(4096)
            self.server_pubkey = rsa.PublicKey.load_pkcs1(server_pub_pem)
            
            # Enviar nuestra llave pública al servidor
            self.sock.sendall(self.pubkey.save_pkcs1())
            
            # Recibir prompt "Usuario: " con protocolo longitud+datos
            prompt_cifrado = recibir_con_longitud(self.sock)
            rsa.decrypt(prompt_cifrado, self.privkey).decode('utf-8')
            
            # Enviar nombre cifrado con protocolo longitud+datos
            nombre_cifrado = rsa.encrypt(nombre_usuario.encode('utf-8'), self.server_pubkey)
            enviar_con_longitud(self.sock, nombre_cifrado)

            # Recibir prompt "Contrasena: " con protocolo longitud+datos
            prompt_pass_cifrado = recibir_con_longitud(self.sock)
            rsa.decrypt(prompt_pass_cifrado, self.privkey).decode('utf-8')

            # Enviar contraseña cifrada con protocolo longitud+datos
            pass_cifrado = rsa.encrypt(contrasena.encode('utf-8'), self.server_pubkey)
            enviar_con_longitud(self.sock, pass_cifrado)

            # Leer respuesta AUTH_OK o ERROR con protocolo longitud+datos
            resp_cifrado = recibir_con_longitud(self.sock)
            resp = rsa.decrypt(resp_cifrado, self.privkey).decode('utf-8').strip()

            if resp.startswith("ERROR"):
                self.sock.close()
                return False, resp
            
            # AUTH_OK: autenticacion exitosa, el cliente queda conectado
            self.conectado = True
            return True, "Conectado exitosamente (Canal Cifrado RSA)"
        except Exception as e:
            return False, f"Error de conexión: {e}"
        
    """este metodo es para enviar mensajes al servidor TCP usando el socket creado en el init"""
    def enviar_mensaje(self, mensaje):
        if self.conectado:
            try:
                mensaje_cifrado = rsa.encrypt(mensaje.encode('utf-8'), self.server_pubkey)
                enviar_con_longitud(self.sock, mensaje_cifrado)
            except OverflowError:
                print("Error: El mensaje es demasiado largo para ser cifrado con RSA 2048 bits.")
            except Exception as e:
                print(f"Error enviando: {e}")

    """metodo para recibir mensajes del servidor TCP usando el socket creado en el init"""
    def recibir_mensaje(self):
        """Recibe un mensaje completo usando protocolo longitud+datos.
        Garantiza que cada llamada devuelve exactamente un mensaje, sin fusiones de TCP."""
        if self.conectado:
            try:
                msg_cifrado = recibir_con_longitud(self.sock)
                if not msg_cifrado:
                    self.cerrar()
                    return None
                msg_plano = rsa.decrypt(msg_cifrado, self.privkey).decode('utf-8')
                return msg_plano
            except:
                return None
        return None

    def cerrar(self): #cierra la conexion del cliente TCP
        self.conectado = False
        try:
            self.sock.close()
        except:
            pass

"""Este metodo se implemento para que el menu.py pueda ejecutar el cliente TCP sin problemas, ya que el menu.py espera un metodo main() en el archivo cliente_tcp.py 
y asi obtener compatibilidad entre ambos archivos"""
def escucharServidor(cliente_obj):
    while cliente_obj.conectado:
        msg = cliente_obj.recibir_mensaje() #usa el metodo recibir_mensaje del objeto cliente
        if msg:
            print("\n" + msg, end="") #se imprime el mensaje recibido y termina en "" para que no haga salto de linea extra
            print("> ", end="", flush=True) #flush para forzar la impresion inmediata de la linea de comando
        else:
            break

"""Metodo main() para compatibilidad con menu.py y para ejecutar el cliente TCP de forma independiente"""
def main():
    nombre = input("Usuario: ").strip()
    nombre_ok, nombre_err = validar_nombre(nombre)
    if not nombre_ok:
        print(f"Error: {nombre_err}")
        return

    contrasena = input("Contrasena: ").strip()
    pass_ok, pass_err = validar_contrasena(contrasena)
    if not pass_ok:
        print(f"Error: {pass_err}")
        return

    # Solo se crea el socket si los datos son validos
    cliente = ClienteTCP()

    exito, info = cliente.conectar(nombre, contrasena)
    if not exito: #si hubo un error en la conexion o autenticacion se imprime el error y se termina
        print(f"Error: {info}")
        return

    print(info) #imprime el mensaje de conexion exitosa
    threading.Thread(target=escucharServidor, args=(cliente,), daemon=True).start() #inicia un hilo separado para escuchar mensajes del servidor TCP usando el metodo escucharServidor, esto permite que el cliente pueda recibir mensajes del servidor de forma asincrona mientras el usuario sigue interactuando con la linea de comando para enviar mensajes

    print("Comandos:\n /priv usuario mensaje\n /salir")
    while True:
        texto = input("> ").strip()
        if texto == "/salir":
            cliente.cerrar()
            break
        cliente.enviar_mensaje(texto)

if __name__ == "__main__":
    main()