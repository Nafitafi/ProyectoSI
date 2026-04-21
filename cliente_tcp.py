import socket
import threading


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

    def conectar(self, nombre_usuario):
        """Conecta al socket y realiza el 'handshake' inicial del nombre."""
        try:
            self.sock.connect((SERVER_IP, SERVER_PORT))
            
            # El servidor envía un prompt inicial (lo leemos para limpiar el buffer)
            prompt = self.sock.recv(1024).decode()
            
            # Enviamos el nombre inmediatamente como pide el protocolo
            self.sock.sendall(nombre_usuario.encode()) #envia el nombre de usuario al servidor
            self.conectado = True #si se conecta bien, marca como conectado
            return True, "Conectado exitosamente"
        except Exception as e:
            return False, f"Error de conexión: {e}"
        
    """este metodo es para enviar mensajes al servidor TCP usando el socket creado en el init"""
    def enviar_mensaje(self, mensaje):
        """Envía bytes al servidor"""
        if self.conectado: #solo si esta conectado
            try:
                self.sock.sendall(mensaje.encode()) #se envia el mensaje codificado en bytes al servidor
            except Exception as e:
                print(f"Error enviando: {e}")

    """metodo para recibir mensajes del servidor TCP usando el socket creado en el init"""
    def recibir_mensaje(self):
        """Intenta recibir mensajes. Retorna el mensaje o None si falla."""
        if self.conectado:
            try:
                msg = self.sock.recv(4096).decode() #el mesnaje es recibido y decodificado
                if not msg:
                    self.cerrar() #se cierra la conexion del cliente si no hay mensaje
                    return None
                return msg #devuelve el mensaje recibido
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
    cliente = ClienteTCP() #crea el objeto cliente TCP
    # Simulación del input original
    # Primero conectamos 'físicamente' para recibir el banner
    cliente.sock.connect((SERVER_IP, SERVER_PORT)) 
    banner = cliente.sock.recv(1024).decode() #el banner es el mensaje inicial del servidor, o sea aparece "Usuario: "
    nombre = input(banner) #pide el nombre de usuario al usuario
    # Enviamos el nombre al servidor
    cliente.sock.sendall(nombre.encode())
    cliente.conectado = True #ahora si esta conectado

    #Iniciamos el hilo para escuchar mensajes del servidor
    threading.Thread(target=escucharServidor, args=(cliente,), daemon=True).start()

    print("Comandos:\n /priv usuario mensaje\n /salir")
    while True:
        texto = input("> ").strip()
        if texto == "/salir":
            cliente.cerrar()
            break
        cliente.enviar_mensaje(texto)

if __name__ == "__main__":
    main()
    