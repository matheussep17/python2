import argparse, uuid
from .db import connect, init_db
from .server import hashed

parser=argparse.ArgumentParser(description='Cria a primeira igreja e administrador')
parser.add_argument('--name', required=True); parser.add_argument('--email', required=True); parser.add_argument('--password', required=True)
args=parser.parse_args(); init_db(); church_id=str(uuid.uuid4())
with connect() as db:
    db.execute('INSERT INTO churches(id,name) VALUES(?,?)',(church_id,args.name)); db.execute('INSERT INTO users(church_id,email,password_hash,role) VALUES(?,?,?,?)',(church_id,args.email.lower(),hashed(args.password),'owner'))
print(f'ID da igreja: {church_id}'); print(f'E-mail: {args.email.lower()}'); print('Administrador criado com sucesso.')
