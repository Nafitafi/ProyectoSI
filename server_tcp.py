"""Servidor TCP para chat multiusuario con mensajes privados y grupales,
se importa la libreria socket para crear el servidor y manejar las conexiones de red
y threading para atender a los clientes de manera simultanea

- import datetime para obtener la fecha y hora actual para los mensajes
- import socket para crear sockets de red
- import threading para manejar multiples clientes simultaneamente
- HOST y PORT definen la direccion y puerto donde el servidor escucha
"""
import datetime
import socket
import threading

HOST = "0.0.0.0"
PORT = 5000

"""se usa UN diccionario para almacenar los clientes conectados, donde la clave es el nombre de usuario
y el valor es el objeto de conexion del socket al que corresponde ese usuario PERMITIENDO enviar mensajes
a cualquier cliente usando solo su nombre.
threading.lock() funciona como un semaforo evitando problemas cuando varios hilos intentan acceder o modificar
el diccionario al mismo tiempo"""
clientes = {}          
lock = threading.Lock()


"""remitente contiene el nombre del usuario que envió el mensaje
Es opcional. Si es None, el mensaje se envía a todos, si tiene valor se excluye al remitente
"""
def broadcast(mensaje, remitente=None):
    """Envia un mensaje a todos los clientes conectados, excepto al remitente si se especifica, 
    de forma que itera sobre el diccionario de clientes y envia el mensaje a cada uno
    se usa un bloque try-catch por si falla un envio, continua con el siguiente cliente
    """

    for nombre, conn in clientes.items():
        if nombre != remitente:
            try:
                conn.sendall(mensaje.encode())
            except:
                pass


def manejarCliente(conn, addr):
    """Maneja la comunicacion con un cliente conectado, registra el nombre de usuario,
    recibe mensajes y los procesa para mensajes privados o grupales, si el cliente se desconecta 
    elimina al cliente de la lista y avisa a los demas. Conn es el socket del cliente y addr es su direccion"""
    nombre = None #hasta que el cliente se registre no hay nombre
    try:
        conn.sendall(b"Usuario: ")
        nombre = conn.recv(1024).decode().strip() #recibe el nombre de usuario del cliente

        with lock:
            """with lock bloquea el acceso para evitar conflictos entre los hilos, despues se verifica
            si el nombre ingresado ya existe, si es asi se envia un error y se cierra la conexion,
            si no, se agrega el cliente al diccionario guardando su conexion"""

            if len(clientes) >= 5:
                conn.sendall(b"ERROR: Servidor lleno. Maximo 5 usuarios.\n")
                conn.close()
                return

            if nombre in clientes:
                conn.sendall(b"ERROR: Usuario ya existe\n")
                conn.close()
                return

            # Registrar cliente
            clientes[nombre] = conn

            # Enviar al nuevo cliente la lista de usuarios ya conectados
            for user in clientes:
                if user != nombre:
                    try:
                        conn.sendall(f"SISTEMA_ADD:{user}\n".encode())
                    except:
                        pass

        """Muestra el servidor de quien se conecto y avisa a todos los clientes que alguien nuevo entro"""
        print(f"[TCP] {nombre} conectado desde {addr}")

        # Avisar a los demas que este usuario se conectó (evento de sistema)
        broadcast(f"SISTEMA_ADD:{nombre}\n", remitente=nombre)
        broadcast(f"*** {nombre} se unio al chat ***\n")

        while True:
            """Bucle principal para recibir mensajes del cliente, espera mensajes del cliengte y si
            el mensaje esta vacio significa que se desconecto, si hay algun error al recibir, se sale del ciclo"""
            msg = conn.recv(1024).decode()
            if not msg:
                break

            msg = msg.strip() #elimina espacios en blanco al inicio y final

            """identifica cel comando del mensaje que es privado, despues separa el destinario y el mensaje
            y por ultimo reconstruye el mensaje completo. Se verifica si el destino existe, envia el mensaje, 
            envia la confirmacion al remitenete y despues salta al sig mensaje con continue"""
            
            fecha = datetime.datetime.now().strftime("%d/%m/%Y %I:%M:%S %p")
            if msg.startswith("/priv"):
                _, destino, *contenido = msg.split() #separa el comando, destinario y mensaje (descompone el mensaje en partes)
                contenido = " ".join(contenido) #toma el resto del mensaje y lo une en una sola cadena para obtener el mensaje completo de forma legible para el usuario

                if destino in clientes:
                    """envia el mensaje privado al destinario y la confirmacion al remitente con la fecha/hora"""
                    clientes[destino].sendall(f"[{fecha}] [PRIVADO de {nombre}] {contenido}\n".encode()) #al recibir el destino se envia el mensaje al cliente correspondiente
                    conn.sendall(f"[PRIVADO para {destino}] [Fecha:{fecha}] {contenido}\n".encode()) #confirma al remitente que se envio el mensaje para que sepa que fue exitoso
                else:
                    conn.sendall(b"ERROR: Usuario no encontrado\n")
                continue

            """envia mensajes grupales a todos los clientes conectados con la fecha/hora actual"""    
            broadcast(f"[{nombre}] [Fecha:{fecha}] {msg}\n", remitente=nombre)

    except:
        pass
   
    finally:
        # Eliminar cliente y notificar a los demas
        with lock: #bloquea el acceso al diccionario para evitar conflictos
            if nombre in clientes:
                del clientes[nombre] #elimina al cliente del diccionario

        # Notificar evento de sistema y mensaje legible
        broadcast(f"SISTEMA_DEL:{nombre}\n")
        broadcast(f"*** {nombre} salio del chat ***\n")
        print(f"[TCP] {nombre} desconectado")
        conn.close()

"""este metodo esta declarado al final ya que primero se definen las funciones que maneja el servidor por si pasa algun error asegurandonos que 
todas las funciones esten definidas antes de usarlas
"""
def main():
    """Configura e inicia el servidor creando un socket TCP despues lo asocia al puerto y 
    pone al servidor en modo escucha
    """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    
    server.settimeout(1) #establece un tiempo de espera para aceptar conexiones, permitiendo manejar interrupciones para que el servidor pueda cerrarse limpiamente 

    print(f"[TCP] Servidor escuchando en {HOST}:{PORT}")

    try:
        while True:
            try:
                conn, addr = server.accept() #acepta una nueva conexion entrante
                threading.Thread(target=manejarCliente, args=(conn, addr), daemon=True).start() #target es la funcion que maneja al cliente, 
                #args son los argumentos que recibe la funcion y daemon=True permite que los hilos se cierren automaticamente al cerrar el programa principal

            except socket.timeout: #si no hay conexiones en el tiempo de espera, continua el bucle
                pass  

    except KeyboardInterrupt: #captura la interrupcion del teclado (Ctrl+C) para cerrar el servidor limpiamente
        print("\nCerrando servidor...")
    finally:
        """"Cierra el socket del servidor al terminar"""
        server.close()


if __name__ == "__main__":
    main()
