import socket
import threading
import rsa


SERVER_IP = "127.0.0.1"
SERVER_PORT = 5000

"""Clase ClienteTCP maneja la conexion TCP con el servidor, envio y recepcion de mensajes. se trata como objeto ya que
permite manejar mejor la conexion y sus estados, asi hay un solo socket por cliente y se puede reutilizar el objeto para
diferentes operacionees como conectar, enviar, recibir y cerrar la conexion
asi no se crean multiples sockets innecesarios, no hay errores de confusion entre sockets y se mantiene el estado de la conexion
"""
class ClienteTCP: #Clase para manejar la conexion TCP con el servidor
    def __init__(self): #Inicializa el socket TCP
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        self.conectado = False #False hasta que se conecte
        
        self.pubkey, self.privkey = rsa.newkeys(2048) #genera un par de claves RSA para este cliente, la clave publica se envia al servidor para que pueda cifrar mensajes privados para este cliente, y la clave privada se usa para descifrar mensajes privados recibidos del servidor
        self.server_pubkey = None #la clave publica del servidor se recibira al conectar y se guardara aqui para cifrar mensajes privados que se envien al servidor

    def conectar(self, nombre_usuario):
        """Conecta al socket y realiza el 'handshake' inicial del nombre."""
        try:
            self.sock.connect((SERVER_IP, SERVER_PORT))
            
            # Recibir llave pública del servidor
            server_pub_pem = self.sock.recv(2048)
            self.server_pubkey = rsa.PublicKey.load_pkcs1(server_pub_pem)
            
            # Enviar nuestra llave pública al servidor
            self.sock.sendall(self.pubkey.save_pkcs1())
            
            # Recibir el prompt "Usuario: " (viene cifrado) y descifrarlo
            prompt_cifrado = self.sock.recv(2048)
            prompt = rsa.decrypt(prompt_cifrado, self.privkey).decode('utf-8')
            
            # Enviar nuestro nombre de usuario CIFRADO al servidor
            nombre_cifrado = rsa.encrypt(nombre_usuario.encode('utf-8'), self.server_pubkey)
            self.sock.sendall(nombre_cifrado)
            
            self.conectado = True
            return True, "Conectado exitosamente (Canal Cifrado RSA)"
        except Exception as e:
            return False, f"Error de conexión: {e}"
        
    """este metodo es para enviar mensajes al servidor TCP usando el socket creado en el init"""
    def enviar_mensaje(self, mensaje):
        if self.conectado:
            try:
                mensaje_cifrado = rsa.encrypt(mensaje.encode('utf-8'), self.server_pubkey) #cifra el mensaje usando la clave publica del servidor para que solo el servidor pueda descifrarlo con su clave privada
                self.sock.sendall(mensaje_cifrado) #envia el mensaje cifrado al servidor
            except OverflowError:
                print("Error: El mensaje es demasiado largo para ser cifrado con RSA 2048 bits.") #RSA tiene un limite de tamaño para los mensajes que puede cifrar, si el mensaje es demasiado largo se lanza esta excepcion.
            except Exception as e:
                print(f"Error enviando: {e}")

    """metodo para recibir mensajes del servidor TCP usando el socket creado en el init"""
    def recibir_mensaje(self):
        """Intenta recibir mensajes. Retorna el mensaje o None si falla."""
        if self.conectado:
            try:
                msg_cifrado = self.sock.recv(4096) 
                if not msg_cifrado:
                    self.cerrar()
                    return None
                
                # Desciframos usando nuestra llave privada
                msg_plano = rsa.decrypt(msg_cifrado, self.privkey).decode('utf-8')
                return msg_plano
            except:
                return None #no envia nada si falla
        return None

    def cerrar(self): #cierra la conexion del cliente TCP
        # Intentar notificar al servidor que nos vamos
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
    cliente = ClienteTCP() #crea una instancia del cliente TCP, esto inicializa el socket y las claves RSA
    
    cliente.sock.connect((SERVER_IP, SERVER_PORT))  #conecta el socket al servidor TCP
    
    server_pub_pem = cliente.sock.recv(2048) #recibe la clave publica del servidor TCP en formato PEM, esta clave se usara para cifrar mensajes privados que se envien al servidor TCP
    cliente.server_pubkey = rsa.PublicKey.load_pkcs1(server_pub_pem) #carga la clave publica del servidor en formato PEM a un objeto de clave RSA para usarlo en el cifrado
    
    cliente.sock.sendall(cliente.pubkey.save_pkcs1()) #envia la clave publica del cliente al servidor TCP, esto permite que el servidor pueda cifrar mensajes privados para este cliente usando esta clave
    
    prompt_cifrado = cliente.sock.recv(2048) #recibe el prompt "Usuario: " cifrado por el servidor TCP, este prompt se usara para pedir al usuario su nombre de usuario
    banner = rsa.decrypt(prompt_cifrado, cliente.privkey).decode('utf-8') #descifra el prompt usando la clave privada del cliente.
    nombre = input(banner) 
    
    nombre_cifrado = rsa.encrypt(nombre.encode('utf-8'), cliente.server_pubkey) #cifra el nombre de usuario usando la clave publica del servidor TCP para que solo el servidor pueda descifrarlo con su clave privada, esto es parte del "handshake" inicial para registrar el nombre de usuario en el servidor
    cliente.sock.sendall(nombre_cifrado) #envia el nombre de usuario cifrado al servidor TCP para que el servidor pueda registrar este cliente con ese nombre de usuario
    
    cliente.conectado = True #marca el cliente como conectado, esto permite que el hilo de escucha del servidor se mantenga activo y pueda recibir mensajes del servidor de forma asíncrona

    threading.Thread(target=escucharServidor, args=(cliente,), daemon=True).start() #inicia un hilo separado para escuchar mensajes del servidor TCP usando el metodo escucharServidor, esto permite que el cliente pueda recibir mensajes del servidor de forma asíncrona mientras el usuario sigue interactuando con la linea de comando para enviar mensajes

    print("Comandos:\n /priv usuario mensaje\n /salir")
    while True:
        texto = input("> ").strip()
        if texto == "/salir":
            cliente.cerrar()
            break
        cliente.enviar_mensaje(texto)

if __name__ == "__main__":
    main()
    