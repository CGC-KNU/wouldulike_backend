# import psycopg2

# # 연결 테스트
# try:
#     conn = psycopg2.connect(
#         dbname='dev',  # 네임스페이스 데이터베이스 이름
#         user='admin',  # Redshift Serverless 사용자 이름
#         password='Redshiftadmin1!',  # 사용자 비밀번호
#         host='default-workgroup.626635447510.ap-northeast-2.redshift-serverless.amazonaws.com',  # 워크그룹 엔드포인트
#         port=5439  # Redshift 기본 포트
#     )
#     print("Connection successful!")
#     conn.close()
# except Exception as e:
#     print(f"Connection failed: {e}")

import psycopg2

try:
    conn = psycopg2.connect(
        dbname='dev',
        user='admin',
        password='Redshiftadmin1!',
        host='default-workgroup.626635447510.ap-northeast-2.redshift-serverless.amazonaws.com',
        port=5439
    )
    cur = conn.cursor()
    cur.execute("SELECT * FROM restaurant_new LIMIT 10;")
    rows = cur.fetchall()
    for row in rows:
        print(row)
    conn.close()
except Exception as e:
    print(f"Connection failed: {e}")
