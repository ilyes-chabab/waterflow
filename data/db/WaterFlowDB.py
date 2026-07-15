import hashlib
import os
import sqlite3

class WaterFlowDB:
    def __init__(self, db_name=None):
        if db_name is None:
            db_name = os.path.join(os.path.dirname(os.path.abspath(__file__)), "waterflow.db")
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.enable_foreign_keys()
        self.create_tables()

    def enable_foreign_keys(self):
        self.cursor.execute("PRAGMA foreign_keys = ON")

    def create_tables(self):
        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            api_key TEXT,
            right TEXT,
            is_active INTEGER DEFAULT 1                        
        )
        """)

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS prediction (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            ph REAL,
            Hardness REAL,
            Solids REAL,
            Chloramines REAL,
            Sulfate REAL,
            Conductivity REAL,
            Organic_carbon REAL,
            Trihalomethanes REAL,
            Turbidity REAL,
            Potability BOOLEAN,
            source TEXT DEFAULT 'manuel',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """)
        self._ensure_prediction_columns()

        self.cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            endpoint TEXT,
            method TEXT,
            status INTEGER,
            duration REAL,
            ip TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """)

        self.conn.commit()

    def _ensure_prediction_columns(self):
        """Migration douce : ajoute les colonnes 'source' et 'created_at'
        si la table 'prediction' existait déjà sans elles (anciennes bases)."""
        self.cursor.execute("PRAGMA table_info(prediction)")
        existing_cols = [row[1] for row in self.cursor.fetchall()]

        if "source" not in existing_cols:
            self.cursor.execute(
                "ALTER TABLE prediction ADD COLUMN source TEXT DEFAULT 'manuel'"
            )
        if "created_at" not in existing_cols:
            self.cursor.execute(
                "ALTER TABLE prediction ADD COLUMN created_at TEXT"
            )
        self.cursor.execute("PRAGMA table_info(users)")
        existing_user_cols = [row[1] for row in self.cursor.fetchall()]
        if "is_active" not in existing_user_cols:
            self.cursor.execute("ALTER TABLE users ADD COLUMN is_active INTEGER DEFAULT 1")
            self.conn.commit()

    # users

    def add_user(self, username, api_key, right):
        self.cursor.execute("""
        INSERT INTO users (username, api_key, right)
        VALUES (?, ?, ?)
        """, (username, api_key, right))
        self.conn.commit()

    def update_user(self, user_id, username, api_key, right):
        self.cursor.execute("""
        UPDATE users
        SET username = ?, api_key = ?, right = ?
        WHERE id = ?
        """, (username, api_key, right, user_id))
        self.conn.commit()

    def delete_user(self, user_id):
        # 1. Supprimer toutes les prédictions de cet utilisateur
        self.cursor.execute("""
        DELETE FROM prediction
        WHERE user_id = ?
        """, (user_id,))

        # 2. Option RGPD pour les logs d'audit : anonymiser plutôt que supprimer
        # Cela permet de conserver l'historique de l'audit sans bloquer la suppression
        self.cursor.execute("""
        UPDATE audit_logs
        SET user_id = NULL
        WHERE user_id = ?
        """, (user_id,))

        # 3. Supprimer enfin l'utilisateur
        self.cursor.execute("""
        DELETE FROM users
        WHERE id = ?
        """, (user_id,))
        
        self.conn.commit()

    def get_users(self):
        self.cursor.execute("SELECT * FROM users")
        return self.cursor.fetchall()
    
    def rotate_user_key(self, user_id: int, new_hashed_key: str):
        self.cursor.execute("""
        UPDATE users
        SET api_key = ?, is_active = 1
        WHERE id = ?
        """, (new_hashed_key, user_id))
        self.conn.commit()
    # prédiction

    def add_prediction(self, user_id, ph, hardness, solids, chloramines,
                        sulfate, conductivity, organic_carbon,
                        trihalomethanes, turbidity, potability, source="manuel"):

        self.cursor.execute("""
        INSERT INTO prediction (
            user_id, ph, Hardness, Solids, Chloramines, Sulfate,
            Conductivity, Organic_carbon, Trihalomethanes, Turbidity, Potability,
            source, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """, (
            user_id, ph, hardness, solids, chloramines,
            sulfate, conductivity, organic_carbon,
            trihalomethanes, turbidity, potability, source
        ))

        self.conn.commit()
        return self.cursor.lastrowid

    def update_prediction(self, prediction_id, ph, hardness, potability):
        self.cursor.execute("""
        UPDATE prediction
        SET ph = ?, Hardness = ?, Potability = ?
        WHERE id = ?
        """, (ph, hardness, potability, prediction_id))
        self.conn.commit()

    def delete_prediction(self, prediction_id):
        self.cursor.execute("""
        DELETE FROM prediction
        WHERE id = ?
        """, (prediction_id,))
        self.conn.commit()

    def get_predictions(self):
        self.cursor.execute("SELECT * FROM prediction")
        return self.cursor.fetchall()
    
    def get_predictions_by_user(self, user_id):
        self.cursor.execute("SELECT * FROM prediction WHERE user_id = ?", (user_id,))
        return self.cursor.fetchall()

    def get_all_predictions_filtered(self, client_id=None, source=None,
                                      date_from=None, date_to=None, zone=None):
        """Récupère tous les prélèvements (jointure avec users) pour le
        dashboard Quality_Analyst, avec filtres optionnels.
        Retourne une liste de tuples :
        (id, user_id, username, role, ph, hardness, solids, chloramines,
         sulfate, conductivity, organic_carbon, trihalomethanes, turbidity,
         potability, source, created_at)
        """
        query = """
        SELECT
            p.id, p.user_id, u.username, u.right,
            p.ph, p.Hardness, p.Solids, p.Chloramines, p.Sulfate,
            p.Conductivity, p.Organic_carbon, p.Trihalomethanes, p.Turbidity,
            p.Potability, p.source, p.created_at
        FROM prediction p
        LEFT JOIN users u ON u.id = p.user_id
        WHERE 1=1
        """
        params = []

        if client_id:
            query += " AND p.user_id = ?"
            params.append(client_id)
        if source:
            query += " AND p.source = ?"
            params.append(source)
        if date_from:
            query += " AND date(p.created_at) >= date(?)"
            params.append(date_from)
        if date_to:
            query += " AND date(p.created_at) <= date(?)"
            params.append(date_to)
        if zone:
            # 'zone' suppose une colonne future sur users (ex: u.zone).
            # Laissé en place pour évolution ; ignoré si la colonne n'existe pas.
            query += " AND u.username LIKE ?"
            params.append(f"%{zone}%")

        query += " ORDER BY p.created_at DESC"

        self.cursor.execute(query, params)
        return self.cursor.fetchall()
    
    # Log

    def add_audit_log(self, user_id: int | None, endpoint: str, method: str, status: int, duration: float, ip: str):
        self.cursor.execute("""
        INSERT INTO audit_logs (user_id, endpoint, method, status, duration, ip)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, endpoint, method, status, duration, ip))
        self.conn.commit()

    def get_audit_logs(self):
        self.cursor.execute("""
        SELECT id, user_id, endpoint, method, status, duration, ip, created_at 
        FROM audit_logs 
        ORDER BY id DESC
        """)
        return self.cursor.fetchall()

    def close(self):
        self.conn.close()