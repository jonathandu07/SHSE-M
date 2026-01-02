import sqlite3
import os
from cryptography.fernet import Fernet
import json

class SecureDatabase:
    def __init__(self, db_path="shse_technical_data.db", key_path="secret.key"):
        self.db_path = os.path.join(os.path.dirname(__file__), db_path)
        self.key_path = os.path.join(os.path.dirname(__file__), key_path)
        self.key = self._load_or_generate_key()
        self.cipher = Fernet(self.key)
        self._init_db()

    def _load_or_generate_key(self):
        """Charge ou génère une clé AES (Fernet)."""
        if os.path.exists(self.key_path):
            with open(self.key_path, "rb") as key_file:
                return key_file.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_path, "wb") as key_file:
                key_file.write(key)
            return key

    def _init_db(self):
        """Initialise le schéma de la base de données."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table Pieces : Liste des pièces (noms en clair pour recherche)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pieces (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Table Specs : Données techniques (Valeurs chiffrées)
        # On stocke tout le dictionnaire d'attributs chiffré dans un BLOB ou TEXT
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS specs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                piece_id INTEGER,
                data_encrypted BLOB,
                FOREIGN KEY(piece_id) REFERENCES pieces(id)
            )
        ''')
        
        conn.commit()
        conn.close()

    def _encrypt(self, data_dict):
        """Chiffre un dictionnaire Python en bytes."""
        json_data = json.dumps(data_dict).encode('utf-8')
        return self.cipher.encrypt(json_data)

    def _decrypt(self, encrypted_data):
        """Déchiffre bytes -> dictionnaire."""
        decrypted_json = self.cipher.decrypt(encrypted_data)
        return json.loads(decrypted_json.decode('utf-8'))

    def save_piece(self, piece_obj):
        """Sauvegarde une instance de pièce et ses attributs."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # 1. Insert or Ignore Piece Name
        cursor.execute("INSERT OR IGNORE INTO pieces (name) VALUES (?)", (piece_obj.nom,))
        conn.commit()
        
        # 2. Get ID
        cursor.execute("SELECT id FROM pieces WHERE name = ?", (piece_obj.nom,))
        piece_id = cursor.fetchone()[0]

        # 3. Prepare Data (exclude methods, keep vars)
        # On ne garde que les attributs publics (pas _ ou méthodes)
        data = {k: v for k, v in vars(piece_obj).items() if not k.startswith('_')}
        
        encrypted_blob = self._encrypt(data)

        # 4. Update or Insert Specs
        # On supprime l'ancienne version pour garder l'historique propre ou on update
        cursor.execute("DELETE FROM specs WHERE piece_id = ?", (piece_id,))
        cursor.execute("INSERT INTO specs (piece_id, data_encrypted) VALUES (?, ?)", (piece_id, encrypted_blob))

        conn.commit()
        conn.close()
        print(f"[BDD] Pièce '{piece_obj.nom}' sauvegardée et chiffrée.")

    def get_piece_data(self, piece_name):
        """Récupère et déchiffre les données d'une pièce."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM pieces WHERE name = ?", (piece_name,))
        res = cursor.fetchone()
        if not res:
            conn.close()
            return None
        
        piece_id = res[0]
        cursor.execute("SELECT data_encrypted FROM specs WHERE piece_id = ?", (piece_id,))
        res_spec = cursor.fetchone()
        conn.close()
        
        if res_spec:
            return self._decrypt(res_spec[0])
        return None

    def get_all_pieces(self):
        """Retourne toutes les pièces déchiffrées."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM pieces")
        names = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        all_data = {}
        for n in names:
            all_data[n] = self.get_piece_data(n)
        return all_data
