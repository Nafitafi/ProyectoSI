"""Cliente UDP simple: envía el nombre al servidor y permite enviar/recibir mensajes.

Provee una clase `ClienteUDP` con métodos para conectar, enviar, recibir y cerrar.
Incluye también funciones de compatibilidad para uso en terminal (`escuchar` y `main`).
"""

import socket
import threading

SERVER_IP = "127.0.0.1"
SERVER_PORT = 6000

class ClienteUDP:
    """socket UDP simple para enviar y recibir mensajes de un servidor UDP. sock.bind usa un puerto aleatorio para
    cada cliente de forma que varios clientes puedan correr en la misma máquina. esto hace que en el modulo de app_gui.py 
    no sea necesario pedir un puerto al usuario.
    - self.conectado: indica si el cliente está "conectado" (registrado) en el servidor UDP.
    """
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("", 0)) #Puerto aleatorio
        self.conectado = False

    def conectar(self, nombre_usuario):
        """En UDP no hay conexión real, pero enviamos el nombre para registrarnos.
        Devuelve `(True, mensaje)` si se envía correctamente, o `(False, error)` si falla.
        """
        try:
            self.sock.sendto(nombre_usuario.encode(), (SERVER_IP, SERVER_PORT)) #envia el nombre al servidor UDP
            self.conectado = True
            return True, "Registrado en UDP"
        except Exception as e:
            return False, f"Error UDP: {e}"
    """enviar_mensaje y recibir_mensaje son compatibles con la interfaz para facilitar su uso en app_gui.py
    self.conectado indica si el cliente esta registrado en el servidor UDP, si no lo esta, no se pueden enviar o recibir mensajes
    """
    def enviar_mensaje(self, mensaje):
        if self.conectado:
            try:
                self.sock.sendto(mensaje.encode(), (SERVER_IP, SERVER_PORT)) #envia el mensaje al servidor UDP
            except Exception as e:
                print(f"Error enviando UDP: {e}")
    """Intenta recibir mensajes. Retorna el mensaje o None si falla. 
    - data, addr = self.sock.recvfrom(4096) recibe datos y la direccion del remitente
    - self.conectado indica si el cliente esta registrado en el servidor UDP y devuelve data.decode() que es el mensaje recibido
    si no, devuelve None
    """
    def recibir_mensaje(self):
        if self.conectado:
            try:
                data, addr = self.sock.recvfrom(4096)
                return data.decode()
            except:
                return None
        return None
    """Cierra el socket UDP y marca el cliente como desconectado con self.conectado = False
    y despues en un bloque try-except intenta cerrar el socket"""
    def cerrar(self):
        # Intentar notificar al servidor que nos vamos
        try:
            if self.conectado:
                try:
                    self.sock.sendto(b"/salir", (SERVER_IP, SERVER_PORT)) #realiza un envio al servidor UDP avisando que se va
                except:
                    pass
        except:
            pass

        self.conectado = False
        try:
            self.sock.close()
        except:
            pass


def escuchar(cliente_obj):
    """Bucle de escucha compatible con terminal.

    Ejecuta `cliente_obj.recibir_mensaje()` en un bucle mientras `cliente_obj.conectado` es True
    Los mensajes se imprimen por consola.
    """

    while cliente_obj.conectado:
        msg = cliente_obj.recibir_mensaje()
        if msg:
            print("\n" + msg)
            print("> ", end="", flush=True)

def main():
    """Función auxiliar para ejecutar el cliente UDP desde la terminal.

    Crea la instancia, solicita el nombre, registra al usuario y entra en el bucle
    de envío de mensajes. Ejecuta `escuchar` en un hilo daemon para mostrar recibidos.
    """

    cliente = ClienteUDP()
    nombre = input("Tu nombre de usuario: ")
    cliente.conectar(nombre)

    """target=escuchar, args=(cliente,), daemon=True inicia un hilo que ejecuta la funcion escuchar pasando el objeto cliente como argumento, 
    el hilo es daemon para que termine cuando el programa principal termine"""
    threading.Thread(target=escuchar, args=(cliente,), daemon=True).start()

    print("Comandos:\n/priv usuario mensaje\n/salir")
    while True:
        msg = input("> ").strip()
        if msg == "/salir":
            # avisar al servidor antes de cerrar
            try:
                cliente.enviar_mensaje("/salir")
            except:
                pass
            cliente.cerrar()
            break
        cliente.enviar_mensaje(msg)

if __name__ == "__main__":
    main()