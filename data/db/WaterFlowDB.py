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
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """)

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
                        trihalomethanes, turbidity, potability):

        self.cursor.execute("""
        INSERT INTO prediction (
            user_id, ph, Hardness, Solids, Chloramines, Sulfate,
            Conductivity, Organic_carbon, Trihalomethanes, Turbidity, Potability
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_id, ph, hardness, solids, chloramines,
            sulfate, conductivity, organic_carbon,
            trihalomethanes, turbidity, potability
        ))

        self.conn.commit()

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