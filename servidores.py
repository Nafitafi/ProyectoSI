"""
Archivo: servidores.py 
Inicia el servidor TCP.
"""
import server_tcp
 
def main():
    print("Iniciando servidor TCP...\nPresiona CTRL+C para detener.")
    try:
        # Llama a la función principal de tu servidor TCP directamente
        server_tcp.main()
    except KeyboardInterrupt:
        print("\nCerrando servidor...")
 
if __name__ == "__main__":
    main()
 