import psycopg2

try:
    connection = psycopg2.connect(
        dbname="alua",
        user="postgres",
        password="Abkrsy11!@",
        host="localhost",
        port="5433"  # или 5432, если используете стандартный порт
    )
    cursor = connection.cursor()
    cursor.execute("SELECT version();")
    record = cursor.fetchone()
    print("You are connected to - ", record, "\n")
except Exception as error:
    print("Error while connecting to PostgreSQL", error)
finally:
    if connection:
        cursor.close()
        connection.close()
        print("PostgreSQL connection is closed")
