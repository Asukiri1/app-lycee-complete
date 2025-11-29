# db_manager.py
import sqlite3
import re



class DBManager:
    # Classe pour gérer les opérations sur la base de données SQLite.

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self._create_tables()
        self.limit = None

    def _create_tables(self):
        # Crée les tables nécessaires dans la base de données.
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT,
                timestamp TEXT,
                computer TEXT,
                user TEXT,
                UNIQUE(event, timestamp, computer, user)
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS imported_files (
                filename TEXT PRIMARY KEY
            )
        ''')
        
        # --- AJOUT DES INDEX ---
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_computer ON sessions (computer)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions (user)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_event ON sessions (event)')
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_timestamp ON sessions (timestamp)')
        # Un index composite pour les sous-requêtes complexes
        self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_sessions_comp_user_event_time ON sessions (computer, user, event, timestamp)')
        # --- FIN AJOUT DES INDEX ---
        
        self.conn.commit()

    def is_file_imported(self, filename: str) -> bool:
        # Vérifie si un fichier a déjà été importé.
        self.cursor.execute("SELECT filename FROM imported_files WHERE filename = ?", (filename,))
        return self.cursor.fetchone() is not None

    def mark_file_imported(self, filename: str):
        # Marque un fichier comme importé dans la base de données.
        self.cursor.execute("INSERT INTO imported_files (filename) VALUES (?)", (filename,))

    def insert_session(self, event: str, timestamp: str, computer: str, user: str):
        # Insère une session dans la table sessions.
        try:
            self.cursor.execute(
                "INSERT INTO sessions (event, timestamp, computer, user) VALUES (?, ?, ?, ?)",
                (event, timestamp, computer, user)
            )
        except sqlite3.IntegrityError:
            # Ignorer les doublons en cas de violation de contrainte UNIQUE
            pass

    def fetch_sessions(self):
        # Récupère toutes les sessions de la base de données.
        self.cursor.execute("SELECT * FROM sessions")
        return self.cursor.fetchall()
    
    def fetch_all_computers(self):
        # Fetch all distinct computers from the sessions table
        self.cursor.execute("SELECT DISTINCT computer FROM sessions")
        return [row[0] for row in self.cursor.fetchall()]


    def search_sessions(self, query):
        # Recherche les sessions contenant le terme de recherche.
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM sessions
            WHERE event LIKE ? OR timestamp LIKE ? OR computer LIKE ? OR user LIKE ?
        """, (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%'))
        return cursor.fetchall()


    def fetch_computer_usage(self):
        # Récupère le pourcentage d'utilisation de chaque ordinateur.
        self.cursor.execute("""
            SELECT computer, SUM(session_duration) AS total_usage
            FROM (
                SELECT
                s1.computer,
                (
                    (julianday(
                        (SELECT MIN(s2.timestamp) 
                         FROM sessions s2 
                         WHERE s2.computer = s1.computer 
                         AND s2.user = s1.user 
                         AND s2.event = 'LOGOFF' 
                         AND s2.timestamp > s1.timestamp)
                    ) - julianday(s1.timestamp)) * 86400
                ) AS session_duration,
                (
                    (julianday(
                        (SELECT MIN(s2.timestamp) 
                         FROM sessions s2 
                         WHERE s2.computer = s1.computer 
                         AND s2.user = s1.user 
                         AND s2.event = 'LOGOFF' 
                         AND s2.timestamp > s1.timestamp)
                    ) - julianday(s1.timestamp)) * 86400
                ) AS raw_duration_seconds
                FROM sessions s1
                WHERE s1.event = 'LOGON'
                AND (SELECT MIN(s2.timestamp) 
                     FROM sessions s2 
                     WHERE s2.computer = s1.computer 
                     AND s2.user = s1.user 
                     AND s2.event = 'LOGOFF' 
                     AND s2.timestamp > s1.timestamp) IS NOT NULL
            ) AS sessions_durations
            WHERE raw_duration_seconds <= 86400 
            GROUP BY computer
        """)
        results = self.cursor.fetchall()
        usage_data = {computer: total_usage if total_usage is not None else 0.0 for computer, total_usage in results}
        total_usage_all = sum(usage_data.values())
        usage_percentage = {computer: round((usage / total_usage_all) * 100, 2) for computer, usage in usage_data.items()}
        return usage_percentage
    
    def fetch_users_per_computer(self) -> dict:
        #Récupère le nombre d'utilisateurs distincts par ordinateur
        self.cursor.execute("""
            SELECT computer, COUNT(DISTINCT user) 
            FROM sessions 
            WHERE event = 'LOGON' 
            GROUP BY computer
        """)
        results = self.cursor.fetchall()
        return {computer: count for computer, count in results}
    
    def fetch_time_by_computer_day_week_month(self) -> dict:
        # Requête qui couple chaque LOGON à son premier LOGOFF ultérieur et réfuse les séssions ou la durée est supérieure à 24 heures
        self.cursor.execute("""
            SELECT
                l.computer,
                strftime('%Y-%m-%d', l.timestamp) AS day,
                strftime('%Y-%W', l.timestamp) AS week,
                strftime('%Y-%m', l.timestamp) AS month,
                (julianday(
                    (SELECT MIN(timestamp)
                    FROM sessions
                    WHERE computer = l.computer
                    AND user = l.user
                    AND event = 'LOGOFF'
                    AND timestamp > l.timestamp)
                ) - julianday(l.timestamp)) * 86400 AS session_time_seconds
            FROM sessions l
            WHERE l.event = 'LOGON'
            AND (SELECT MIN(timestamp)
                FROM sessions
                WHERE computer = l.computer
                AND user = l.user
                AND event = 'LOGOFF'
                AND timestamp > l.timestamp) IS NOT NULL
            AND (julianday(
                (SELECT MIN(timestamp)
                FROM sessions
                WHERE computer = l.computer
                AND user = l.user
                AND event = 'LOGOFF'
                AND timestamp > l.timestamp)
            ) - julianday(l.timestamp)) * 86400 <= 86400
        """)
        results = self.cursor.fetchall()
        
        time_data = {}
        for computer, day, week, month, session_time_seconds in results:
            if computer not in time_data:
                time_data[computer] = {'Jour': {}, 'Semaine': {}, 'Mois': {}}
            
            # Ajouter le temps pour le jour
            time_data[computer]['Jour'][day] = time_data[computer]['Jour'].get(day, 0) + session_time_seconds
            # Pour la semaine
            time_data[computer]['Semaine'][week] = time_data[computer]['Semaine'].get(week, 0) + session_time_seconds
            # Pour le mois
            time_data[computer]['Mois'][month] = time_data[computer]['Mois'].get(month, 0) + session_time_seconds
        
        return time_data
    

    def group_computers_by_room(self):
        # Récupère tous les noms d'ordinateurs
        all_computers = self.fetch_all_computers()
        
        # Dictionnaire pour stocker les groupes d'ordinateurs par salle
        rooms = {}

        for computer in all_computers:
            # Normalise le nom en supprimant uniquement les suffixes purement numériques
            normalized = re.sub(r'(-W\d{2,}|\b\d+\b)$', '', computer, flags=re.IGNORECASE)
            
            normalized = normalized.rstrip("-")  # Supprime le tiret à la fin si présent
            # Pour les ordinateurs dont le nom normalisé est non vide, on les regroupe
            if normalized:
                if normalized not in rooms:
                    rooms[normalized] = []
                rooms[normalized].append(computer)

        return rooms  # Retourne tous les groupes, y compris ceux avec un seul ordinateur


    def fetch_users_per_rooms_stats(self):
        # Récupère les groupes d'ordinateurs par salle
        rooms = self.group_computers_by_room()
        
        # Dictionnaire pour stocker le nombre d'utilisateurs par salle
        users_per_room = {}

        for room, computers in rooms.items():
            # Récupère les utilisateurs distincts pour les ordinateurs de cette salle
            placeholders = ', '.join('?' for _ in computers)
            query = f"""
                SELECT COUNT(DISTINCT user)
                FROM sessions
                WHERE computer IN ({placeholders})
            """
            self.cursor.execute(query, computers)
            count = self.cursor.fetchone()[0]
            users_per_room[room] = users_per_room.get(room, 0) + count  # Additionne les utilisateurs pour la salle
        
        return users_per_room

    def fetch_time_per_rooms_stats(self):
        # Récupère les groupes d'ordinateurs par salle
        rooms = self.group_computers_by_room()
        
        # Dictionnaire pour stocker le temps d'utilisation par salle
        time_per_room = {}

        for room, computers in rooms.items():
            # Récupère le temps d'utilisation total pour les ordinateurs de cette salle
            placeholders = ', '.join('?' for _ in computers)
            query = f"""
                SELECT SUM(session_time_seconds)
                FROM (
                    SELECT 
                    l.computer,
                    (julianday(
                        (SELECT MIN(timestamp)
                        FROM sessions
                        WHERE computer = l.computer
                        AND user = l.user
                        AND event = 'LOGOFF'
                        AND timestamp > l.timestamp)
                    ) - julianday(l.timestamp)) * 86400 AS session_time_seconds
                    FROM sessions l
                    WHERE l.event = 'LOGON'
                    AND (SELECT MIN(timestamp)
                        FROM sessions
                        WHERE computer = l.computer
                        AND user = l.user
                        AND event = 'LOGOFF'
                        AND timestamp > l.timestamp) IS NOT NULL
                    AND (julianday(
                        (SELECT MIN(timestamp)
                        FROM sessions
                        WHERE computer = l.computer
                        AND user = l.user
                        AND event = 'LOGOFF'
                        AND timestamp > l.timestamp)
                    ) - julianday(l.timestamp)) * 86400 <= 86400
                ) AS session_times
                WHERE computer IN ({placeholders})
            """
            self.cursor.execute(query, computers)
            total_time_seconds = self.cursor.fetchone()[0]
            time_per_room[room] = time_per_room.get(room, 0) + (total_time_seconds / 3600 if total_time_seconds else 0)  # Additionne le temps pour la salle
        
        return time_per_room

    def fetch_monthly_usage_per_room(self):
        # Récupère les groupes d'ordinateurs par salle
        rooms = self.group_computers_by_room()
        
        # Dictionnaire pour stocker le temps d'utilisation par mois pour chaque salle
        monthly_usage_per_room = {}

        for room, computers in rooms.items():
            # Récupère le temps d'utilisation total par mois pour les ordinateurs de cette salle
            placeholders = ', '.join('?' for _ in computers)
            query = f"""
                SELECT 
                    strftime('%Y-%m', l.timestamp) AS month,
                    SUM((julianday(
                        (SELECT MIN(timestamp)
                        FROM sessions
                        WHERE computer = l.computer
                        AND user = l.user
                        AND event = 'LOGOFF'
                        AND timestamp > l.timestamp)
                    ) - julianday(l.timestamp)) * 86400) / 3600 AS total_hours
                FROM sessions l
                WHERE l.event = 'LOGON'
                AND (SELECT MIN(timestamp)
                    FROM sessions
                    WHERE computer = l.computer
                    AND user = l.user
                    AND event = 'LOGOFF'
                    AND timestamp > l.timestamp) IS NOT NULL
                AND (julianday(
                    (SELECT MIN(timestamp)
                    FROM sessions
                    WHERE computer = l.computer
                    AND user = l.user
                    AND event = 'LOGOFF'
                    AND timestamp > l.timestamp)
                ) - julianday(l.timestamp)) * 86400 <= 86400
                AND l.computer IN ({placeholders})
                GROUP BY month
                ORDER BY month
            """
            self.cursor.execute(query, computers)
            results = self.cursor.fetchall()
            if room not in monthly_usage_per_room:
                monthly_usage_per_room[room] = {}
            for row in results:
                month, total_hours = row
                monthly_usage_per_room[room][month] = monthly_usage_per_room[room].get(month, 0) + total_hours  # Additionne les heures pour chaque mois
        
        return monthly_usage_per_room
    
    def clear_database(self):
        # Supprime toutes les données des tables sessions et imported_files
        self.cursor.execute("DELETE FROM sessions")
        self.cursor.execute("DELETE FROM imported_files")
        self.conn.commit()
    

    def set_limit(self, limit):
        # Définit la limite d'affiche de  résultats pour les requêtes.
        self.limit = limit

    def fetch_limited_data(self, data):
        ## Limite le nombre de résultats affichés.
        if self.limit is not None:
            return dict(list(data.items())[:self.limit])
        return data


    
    def commit(self):
        # Effectue un commit sur la connexion.
        self.conn.commit()

    def close(self):
        # Ferme la connexion à la base de données.
        if self.conn:
            self.conn.close()