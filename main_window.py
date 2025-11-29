# main_window.py
import os
import re
from datetime import datetime
from PyQt6.QtWidgets import QMainWindow, QFileDialog, QMessageBox, QPushButton, QProgressBar
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.uic import loadUi
from db_manager import DBManager
from chart import BarChart


class MainWindow(QMainWindow):
    # Fenêtre principale de l'application de gestion des logs.
    def __init__(self):
        super().__init__()
        ui_path = os.path.join(os.path.dirname(__file__), "gui.ui")  # Update the UI file path
        loadUi(ui_path, self)
        self.bar_chart_window = None
        
        # Initialiser le gestionnaire de base de données
        self.db_manager = DBManager(db_path='logs.db')
        
        # Initialiser le modèle pour le QTableView
        self.model = QStandardItemModel()
        self.tableView.setModel(self.model)

        # Masquer le QTableView et la barre de recherche au démarrage
        self.tableView.hide()
        self.lineEdit.hide()
        
        # Référencer la QProgressBar
        self.progressBarLogImport = self.findChild(QProgressBar, 'progressBarLogImport')
        self.progressBarLogImport.hide()  # Masquer la barre de progression au démarrage

        # Connecter les signaux de l'interface aux slots
        self._setup_signals()

    def _setup_signals(self):
        # Connecte les signaux aux slots appropriés.

        # Connecter les options de tri du menu sort
        self.triDate.clicked.connect(lambda: self.sort_sessions("date"))
        self.triPoste.clicked.connect(lambda: self.sort_sessions("computer"))

        # Connecter les actions de options
        self.statButton.clicked.connect(self.show_charts)
        self.searchLogButton.clicked.connect(self.show_or_hide_search_bar)
        self.lineEdit.returnPressed.connect(self.search_in_logs)  # Connecter le bouton de recherche
        self.resetButton.clicked.connect(self.clear_database)

        # Connecter le bouton d'importation de logs
        self.importLogButton.clicked.connect(self.open_file)
        self.importLogButton_2.clicked.connect(self.open_file)  # Pour le drag and drop
    def sort_sessions(self, criteria: str):
        # Trie les sessions selon le critère fourni.
        if criteria == "name":
            self.model.sort(4)
        elif criteria == "date":
            self.model.sort(2)
        elif criteria == "computer":
            self.model.sort(3)


    
    def clear_database(self):
        # Supprime toutes les données des tables sessions et imported_files
        self.db_manager.clear_database()
        self.lineEdit.clear()
        self.model.removeRows(0, self.model.rowCount())  # Efface les données affichées
        QMessageBox.information(self, "Succès", "La base de données a été vidée avec succès.")
        

    def open_file(self):
        # Ouvre le dialogue de sélection de fichier pour importer les logs.
        file_names, _ = QFileDialog.getOpenFileNames(
            self,
            'Ouvrir fichier(s)',
            os.getcwd(),
            'Fichiers log (*.log)'
        )
        if file_names:
            self.import_logs(file_names)

    def import_logs(self, file_names):
        # Importe les fichiers de logs sélectionnés dans la base de données.
        # Expression régulière pour extraire les informations des lignes de log
        pattern = re.compile(
            r'\[(LOGON\.|LOGOFF)\] (\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}) '
            r'Computer="([^"]+)" User="([^"]+)"'
        )

        total_files = len(file_names)
        self.progressBarLogImport.setMaximum(total_files)
        self.progressBarLogImport.setValue(0)
        self.progressBarLogImport.show()

        already_imported_files = []

        for index, file_name in enumerate(file_names):
            if self.db_manager.is_file_imported(file_name):
                already_imported_files.append(file_name)
                continue

            with open(file_name, "r", encoding="utf-8") as file:
                for line in file:
                    match = pattern.search(line)
                    if match:
                        event = match.group(1).replace('.', '')
                        timestamp = match.group(2)  # format "dd/mm/yyyy hh:mm:ss"
                        dt = datetime.strptime(timestamp, "%d/%m/%Y %H:%M:%S")
                        timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                        computer = match.group(3)
                        user = match.group(4)
                        self.db_manager.insert_session(event, timestamp, computer, user)

            self.db_manager.mark_file_imported(file_name)
            self.progressBarLogImport.setValue(index + 1)

        self.db_manager.commit()
        self.importLogButton_2.hide()  # Masquer le bouton après importation
        self.progressBarLogImport.hide()  # Masquer la barre de progression après importation
        self.display_data()

        if already_imported_files:
            already_imported_files_str = "\n".join(already_imported_files)
            QMessageBox.information(self, "Fichiers deja importé!",
                                    f"Les fichiers suivants sont déja dans la base de données et n'ont pas été importé! :\n{already_imported_files_str}")
        else:
            QMessageBox.information(self, "Opération réussie!",
                                    "Les fichiers ont été importés avec succès dans la base de données.")

    def display_data(self):
        # Affiche les données de la table sessions dans le QTableView.
        self.tableView.show()
        sessions = self.db_manager.fetch_sessions()
        self.model.setHorizontalHeaderLabels(['ID', 'Evenement', 'Date', 'Poste'])  # Exclure 'User'
        self.model.removeRows(0, self.model.rowCount())  # Effacer les données existantes
        for row in sessions:
            # Exclure la colonne 'User' (dernier champ)
            items = [QStandardItem(str(field)) for field in row[:-1]]
            self.model.appendRow(items)
    
    def show_or_hide_search_bar(self):
        # Affiche la barre de recherche ou la cache si on reappui.
        if self.lineEdit.isHidden():
            self.lineEdit.show()
        else:
            self.lineEdit.hide()

    def search_in_logs(self):
        # Recherche dans les logs et affiche les résultats.
        query = self.lineEdit.text()
        results = self.db_manager.search_sessions(query)
        self.model.removeRows(0, self.model.rowCount())  # Effacer les données existantes
        for row in results:
            items = [QStandardItem(str(field)) for field in row[:-1]]  # Exclure 'User'
            self.model.appendRow(items)
    
    def show_charts(self):
        # Crée une fenêtre persistante ou la réutilise si elle existe déjà
        if not self.bar_chart_window or not self.bar_chart_window.isVisible():
            self.bar_chart_window = BarChart()
        self.bar_chart_window.show()

    def closeEvent(self, event):
        # Ferme la connexion à la base de données avant de supprimer le fichier.
        if self.bar_chart_window and self.bar_chart_window.isVisible():
            self.bar_chart_window.close()  # Fermer explicitement BarChart
        self.db_manager.close()
        if os.path.exists('logs.db'):
            try:
                os.remove('logs.db')
            except PermissionError:
                print("Le fichier 'logs.db' est toujours utilisé par un autre processus.")
        event.accept()





# Drag and drop
class importLogButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        # On accepte le drag si les données contiennent des URLs (fichiers)
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        file_names = []
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            if file_path.lower().endswith('.log'):
                file_names.append(file_path)
        if file_names:
            self.window().import_logs(file_names)
            event.acceptProposedAction()
        else:
            event.ignore()

