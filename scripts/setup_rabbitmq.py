from app.mq.connection import create_rabbitmq_connection
from app.mq.topology import declare_order_topology


def main() -> None:
    connection = create_rabbitmq_connection()
    try:
        channel = connection.channel()
        declare_order_topology(channel)
        print("RabbitMQ order topology declared")
    finally:
        connection.close()


if __name__ == "__main__":
    main()
