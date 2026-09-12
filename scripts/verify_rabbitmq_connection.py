from app.mq.connection import create_rabbitmq_connection


def main() -> None:
    connection = create_rabbitmq_connection()
    try:
        print("RabbitMQ connection succeeded")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
