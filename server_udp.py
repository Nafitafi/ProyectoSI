"""Servidor de chat UDP que maneja multiples clientes y permite mensajes privados. El servidorUDP
procesa un mensaje donde: recibe, procesa y envia respuesta """
import socket
import datetime

HOST = "0.0.0.0"
PORT = 6000

"""Se usan diccionarios para almacenar los usuarios conectados. 
usuarios: clave es la direccion del cliente (IP, puerto) y valor es el nombre de usuario, permite identificar al cliente por su direccion
usuariosPorNombre: clave es el nombre de usuario y valor es la direccion del cliente, permite enviar mensajes privados facilmente buscando
la direccion del destinatario por su nombre.
"""
usuarios = {}         
usuariosPorNombre = {}


"""a diferencia de SERVER TCP creamos el metodo main() primero porque es mas sencillo y no requiere hilos adicionales para manejar clientes,
ya que UDP es sin conexion y no mantiene conexiones persistentes con los clientes
"""
def main():
    """Crea el socket UDP donde AF_INET es para IPv4 y SOCK_DGRAM para UDP,
    luego lo enlaza el socket a la direccion y puerto. En un ciclo infinito,
    espera mensajes de los clientes, procesa mensajes privados o grupales, (siempre esta escuhando
    mensajes)"""
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((HOST, PORT))
    
    server.settimeout(1)

    print(f"[UDP] Servidor escuchando en {HOST}:{PORT}")

    try:
        while True:
            """Bucle principal que espera mensajes de los clientes y los procesa"""
            try:
                data, addr = server.recvfrom(4096) #data es el mensaje recibido, addr es la direccion del cliente (IP, puerto)
            except socket.timeout:#si no hay mensajes en el tiempo de espera, continua el bucle
                continue

            texto = data.decode().strip()
            # Si la direccion del cliente no esta en el diccionario, puede ser un registro (nombre)
            if addr not in usuarios:
                # Registro inicial del usuario (texto contiene el nombre)
                nombre_nuevo = texto

                if len(usuarios) >= 5:
                    server.sendto(b"[ERROR] Servidor lleno. Maximo 5 usuarios.", addr)
                    continue

                if nombre_nuevo in usuariosPorNombre:
                    server.sendto(b"[ERROR] Usuario ya existe", addr)
                    continue

                # Informar al nuevo cliente sobre los usuarios ya conectados
                for nombre_existente in usuariosPorNombre.keys(): #keys() obtiene los nombres de los usuarios conectados
                    try:
                        server.sendto(f"SISTEMA_ADD:{nombre_existente}\n".encode(), addr)
                    except:
                        pass

                # Registrar al nuevo cliente
                usuarios[addr] = nombre_nuevo #(IP, PUERTO): NOMBREDELUSUARIO
                usuariosPorNombre[nombre_nuevo] = addr #NOMBREDEUSUARIO (IP, PUERTO)
                print(f"[UDP] {nombre_nuevo} conectado desde {addr}")   

                # Avisar a los demas que se unió (evento de sistema)
                for cliente_addr in usuarios: #mientras recorre los clientes conectados 
                    if cliente_addr != addr: #si no es el nuevo cliente entonces envia la notificacion
                        try:
                            server.sendto(f"SISTEMA_ADD:{nombre_nuevo}\n".encode(), cliente_addr)
                        except:
                            pass

                continue

            # Obtener el nombre del remitente por su direccion
            nombre = usuarios.get(addr)
            if nombre is None:
                # No registrado (ignoramos)
                continue

            # Manejar desconexión explícita por parte del cliente
            if texto == "/salir":
                # Eliminar del registro y notificar a los demas
                try:
                    del usuariosPorNombre[nombre]
                except KeyError:
                    pass
                try:
                    del usuarios[addr] #elimina al usuario del diccionario de usuarios
                except KeyError:
                    pass

                # Notificar evento de sistema
                for cliente_addr in usuarios:
                    try:
                        server.sendto(f"SISTEMA_DEL:{nombre}\n".encode(), cliente_addr)
                        server.sendto(f"*** {nombre} salio del chat ***\n".encode(), cliente_addr)
                    except:
                        pass
                continue

        
            
            """Obtiene la fecha y hora actual en formato dia/mes/año horas:minutos:segundos AM/PM"""
            fecha = datetime.datetime.now().strftime("%d/%m/%Y %I:%M:%S %p")
            
            """para mensajes privados se verifica si el mensaje empieza con /priv, despues se separa el destinatario y el contenido
            se verifica si el destinatario existe, si no existe se envia un mensaje de error al remitente"""
            if texto.startswith("/priv"):
                _, destino, *contenido = texto.split()
                contenido = " ".join(contenido)

                if destino not in usuariosPorNombre:
                    server.sendto(f"[ERROR] Usuario '{destino}' no existe".encode(), addr)
                    continue

                addr_destino = usuariosPorNombre[destino] #addr_destino es la direccion del destinatario y se obtiene del diccionario usuariosPorNombre 
                #para enviar el mensaje privado

                #enviar al destinatario
                server.sendto(f"[PRIVADO de {nombre}] [Fecha:{fecha}] {contenido}".encode(), addr_destino)
                #confirmar al remitente
                server.sendto(f"[PRIVADO para {destino}] [Fecha:{fecha}] {contenido}".encode(), addr)

                continue

            """Si no es priavdo significa que es un mensaje grupal"""
            mensajeFinal = f"[{nombre}] [Fecha:{fecha}] {texto}"

            """envia el mensaje a todos los clientes conectados excepto al remitente"""
            for cliente in usuarios:
                if cliente != addr: #si cliente no es el remitente entonces envia el mensaje
                    server.sendto(mensajeFinal.encode(), cliente)
                    
    #keyboardInterrupt para cerrar el servidor con Ctrl+C
    except KeyboardInterrupt:
        print("\nCerrando servidor UDP...")
    finally:

        server.close()

if __name__ == "__main__":
    main()
