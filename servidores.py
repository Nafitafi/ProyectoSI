"""
Archivo: servidores.py 
Inicia el servidor TCP.
"""
import server_tcp
 
def main():
    print("Iniciando servidor TCP...\nPresiona CTRL+C para detener.")
    try:
        server_tcp.main()
    except KeyboardInterrupt:
        print("\nCerrando servidor...")
 
if __name__ == "__main__":
    main()
 