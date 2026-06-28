import hashlib
import sqlite3

class WaterFlowDB:
    def __init__(self, db_name="data\\db\\waterflow.db"):
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
            right TEXT
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
        CREATE TABLE IF NOT EXISTS performance_metrics (
            id INTEGER PRIMARY KEY,
            prediction_id INTEGER,
            accuracy REAL,
            precision REAL,
            recall REAL,
            f1_score REAL,
            ROCK_SCORE REAL,
            response_time REAL,
            FOREIGN KEY (prediction_id) REFERENCES prediction (id)
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
        self.cursor.execute("""
        DELETE FROM users
        WHERE id = ?
        """, (user_id,))
        self.conn.commit()

    def get_users(self):
        self.cursor.execute("SELECT * FROM users")
        return self.cursor.fetchall()
    
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
    
    # métrics

    def add_metrics(self, prediction_id, accuracy, precision, recall, f1_score,
                    rock_score, response_time):

        self.cursor.execute("""
        INSERT INTO performance_metrics (
            prediction_id, accuracy, precision, recall, f1_score,
            ROCK_SCORE, response_time
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            prediction_id, accuracy, precision, recall, f1_score,
            rock_score, response_time
        ))

        self.conn.commit()

    def update_metrics(self, metrics_id, accuracy, recall):
        self.cursor.execute("""
        UPDATE performance_metrics
        SET accuracy = ?, recall = ?
        WHERE id = ?
        """, (accuracy, recall, metrics_id))
        self.conn.commit()

    def delete_metrics(self, metrics_id):
        self.cursor.execute("""
        DELETE FROM performance_metrics
        WHERE id = ?
        """, (metrics_id,))
        self.conn.commit()

    def get_metrics(self):
        self.cursor.execute("SELECT * FROM performance_metrics")
        return self.cursor.fetchall()

    def close(self):
        self.conn.close()