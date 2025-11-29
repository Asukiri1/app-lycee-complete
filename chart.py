import os
from PyQt6.uic import loadUi
from PyQt6.QtCore import Qt, QStringListModel, QRect, QSize, QRectF
from PyQt6.QtGui import QPainter, QFont, QStandardItem, QStandardItemModel, QImage, QPageSize, QPageLayout
from PyQt6.QtSvg import QSvgGenerator
from PyQt6.QtWidgets import QMainWindow, QVBoxLayout, QScrollArea, QCompleter, QMessageBox, QFileDialog
from PyQt6.QtCharts import QChart, QChartView, QBarSet, QHorizontalBarSeries, QBarCategoryAxis, QValueAxis, QBarSeries
from PyQt6.QtPrintSupport import QPrinter,QPrintDialog, QPrintPreviewDialog
from db_manager import DBManager


class BarChart(QMainWindow):
    def __init__(self):
        super().__init__()
        ui_path = os.path.join(os.path.dirname(__file__), "stat_gui.ui")
        loadUi(ui_path, self)
        self.db_manager = DBManager(db_path='logs.db')
        self._setup_signals()

        # Initialize the completer
        self.completer = QCompleter()
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.lineComputer.setCompleter(self.completer)

        # Initialize the model for displaying the search results
        self.model = QStandardItemModel()

        # Hide the lineEditRoom by default
        self.lineEditRoom.setVisible(False)

        self.sort_descending = True  # Start with descending order by default
        self.last_value_sorted_chart_function = None  # Store the last sortable chart function

    def _setup_signals(self):
        # Connecte les signaux aux slots appropriés.
        self.computer_use_pie.clicked.connect(self.computer_percent_usage_pie)
        self.users_per_computers.clicked.connect(self.user_by_computers_bar)
        self.daily_weekly_monthly.clicked.connect(self.change_page)
        self.exportButton.clicked.connect(self.export_chart)
        self.printButton.clicked.connect(self.print_chart)
        

        # Boutons day/week/months + lineEdit
        self.dayButton.clicked.connect(lambda: self.use_by_day_week_month_line('Jour'))
        self.weekButton.clicked.connect(lambda: self.use_by_day_week_month_line('Semaine'))
        self.monthButton.clicked.connect(lambda: self.use_by_day_week_month_line('Mois'))
        self.lineComputer.textChanged.connect(self.search_in_computers)

        # Stats by room button + line edit
        self.usersPerRoomButton.clicked.connect(self.users_per_rooms_stats)
        self.timePerRoomButton.clicked.connect(self.time_per_rooms_stats)
        self.timePerRoomPerMonthButton.clicked.connect(self.show_line_edit_for_room_selection)
        self.lineEditRoom.returnPressed.connect(self.monthly_usage_per_room_bar)
        self.percentPerRoomButton.clicked.connect(self.percentage_per_rooms_stats)

        #Graph limit buttons + inverse button
        self.limit20Button.clicked.connect(lambda: self.set_limit_and_refresh(20))
        self.limit50Button.clicked.connect(lambda: self.set_limit_and_refresh(50))
        self.limit100Button.clicked.connect(lambda: self.set_limit_and_refresh(100))
        self.noLimitButton.clicked.connect(lambda: self.set_limit_and_refresh(None))
        self.inverseButton.clicked.connect(self.inverse_order)  # Connect the inverse button

    def change_page(self):
        if self.stackedWidget.currentWidget() == self.page:
            self.stackedWidget.setCurrentWidget(self.page_2)
        QMessageBox.information(self, "Attention!",
                                    "Les opérations ou le logon et le logoff est espacé de plus de 24h ne sont pas prises en compte.")
        
            

    def closeEvent(self, event):
        # Fermer la connexion à la base de données lorsque la fenêtre est fermée
        self.db_manager.close()
        event.accept()

    def computer_percent_usage_pie(self):
        self.last_value_sorted_chart_function = self.computer_percent_usage_pie  # Store function reference
        if self.stackedWidget.currentWidget() == self.page_2:
            self.stackedWidget.setCurrentWidget(self.page)
        # Fetch all data
        usage_data = self.db_manager.fetch_computer_usage()

        # Sort all data by percentage in descending order
        sorted_percentage_usage_data = dict(sorted(
            usage_data.items(),
            key=lambda item: item[1],
            reverse=self.sort_descending  # Use the state variable
        ))

        # Apply limit to sorted data
        limited_sorted_data = self.db_manager.fetch_limited_data(sorted_percentage_usage_data)

        # Create QBarSet and categories using limited and sorted data
        bar_set = QBarSet("Pourcentage d'utilisation")
        categories = []
        for computer, percentage in reversed(list(limited_sorted_data.items())):
            bar_set.append(percentage)
            categories.append(computer)

        # Crée une série pour le graphique en barres horizontales
        series = QHorizontalBarSeries()
        series.append(bar_set)
        series.setLabelsVisible(True)
        series.setLabelsPosition(QHorizontalBarSeries.LabelsPosition.LabelsInsideEnd)  # Afficher les étiquettes à l'intérieur des barres
        series.setLabelsFormat("@value%")  

        # Crée un graphique et y ajoute la série
        chart = QChart()
        chart.addSeries(series)
        sort_order_text = "décroissant" if self.sort_descending else "croissant"
        chart.setTitle(f"Pourcentage d'utilisation par poste (Ordre {sort_order_text})")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        # Définir la police du titre pour être plus gros et en gras
        title_font = QFont()
        title_font.setPointSize(16)  # Taille de la police
        title_font.setBold(True)     # Mettre en gras
        chart.setTitleFont(title_font)

        # Définir les axes
        axis_x = QValueAxis()
        axis_x.setTitleText("Pourcentage d'utilisation")
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QBarCategoryAxis()
        axis_y.append(categories)
        axis_y.setTitleText("Postes")
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        # Crée la vue du graphique
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Ajuster la taille du chart_view en fonction du nombre de catégories
        chart_view.setMinimumHeight(50 * len(categories))
        chart_view.setMinimumWidth(800)

        # Crée un QScrollArea pour permettre le défilement vertical
        scroll_area = QScrollArea()
        scroll_area.setWidget(chart_view)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        # Récupère ou crée le layout pour le QFrame ShowGraph
        if self.ShowGraph.layout() is None:
            layout = QVBoxLayout()
            self.ShowGraph.setLayout(layout)
        else:
            layout = self.ShowGraph.layout()
            # Vider le layout existant
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        # Ajoute le scroll_area dans le layout du QFrame
        layout.addWidget(scroll_area)
        self.ShowGraph.show()
    

    def user_by_computers_bar(self):
        self.last_value_sorted_chart_function = self.user_by_computers_bar  # Store function reference
        if self.stackedWidget.currentWidget() == self.page_2:
            self.stackedWidget.setCurrentWidget(self.page)
        # Fetch all data
        usage_data = self.db_manager.fetch_users_per_computer()

        # Sort all data by user count in descending order
        sorted_usage_data = dict(sorted(
            usage_data.items(),
            key=lambda item: item[1],
            reverse=self.sort_descending  # Use the state variable
        ))

        # Apply limit to sorted data
        limited_sorted_data = self.db_manager.fetch_limited_data(sorted_usage_data)

        # Create QBarSet and categories using limited and sorted data
        bar_set = QBarSet("Utilisateurs par poste")
        categories = []
        for computer, count in reversed(list(limited_sorted_data.items())):
            bar_set.append(count)
            categories.append(computer)

        # Create a horizontal bar series
        series = QHorizontalBarSeries()
        series.append(bar_set)
        series.setLabelsVisible(True)
        series.setLabelsPosition(QHorizontalBarSeries.LabelsPosition.LabelsInsideEnd)

        # Create a chart and add the series
        chart = QChart()
        chart.addSeries(series)
        sort_order_text = "décroissant" if self.sort_descending else "croissant"
        chart.setTitle(f"Utilisateurs par poste (Ordre {sort_order_text})")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        # Set title font
        title_font = QFont()
        title_font.setPointSize(16)  # Font size
        title_font.setBold(True)     # Bold font
        chart.setTitleFont(title_font)

        # Define axes
        axis_x = QValueAxis()
        axis_x.setTitleText("Nombre d'utilisateurs distinct")
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QBarCategoryAxis()
        axis_y.append(categories)
        axis_y.setTitleText("Postes")
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        # Create the chart view
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Adjust the chart view size
        chart_view.setMinimumHeight(50 * len(categories))
        chart_view.setMinimumWidth(800)

        # Create a QScrollArea for vertical scrolling
        scroll_area = QScrollArea()
        scroll_area.setWidget(chart_view)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        # Clear the old content of the QFrame ShowGraph and insert the new chart
        if self.ShowGraph.layout() is None:
            layout = QVBoxLayout()
            self.ShowGraph.setLayout(layout)
        else:
            layout = self.ShowGraph.layout()
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        layout.addWidget(scroll_area)
        self.ShowGraph.show()

    
    
    
    
    
    
    
    
    
    def use_by_day_week_month_line(self, period):
        self.last_value_sorted_chart_function = None  # Clear function reference (not value-sorted)
        # Récupérer les données globales
        time_data = self.db_manager.fetch_time_by_computer_day_week_month()

        # Vérifier la validité de la période
        if period not in ['Jour', 'Semaine', 'Mois']:
            raise ValueError(f"Invalid period: {period}")

        # Récupérer le nom (ou l'ID) du poste saisi dans lineComputer
        chosen_computer = self.lineComputer.text().strip().lower()
        # (Vous pouvez décider de gérer la casse différemment selon vos besoins)

        # Filtrer pour ne garder que les données du poste choisi
        filtered_time_data = {}
        for computer_name, usage_dict in time_data.items():
            # On compare en minuscules pour ignorer la casse
            if computer_name.lower() == chosen_computer:
                filtered_time_data[computer_name] = usage_dict

        # Convertir les secondes en heures pour la période demandée
        for computer in filtered_time_data:
            if period in filtered_time_data[computer]:
                for key in filtered_time_data[computer][period]:
                    filtered_time_data[computer][period][key] /= 3600

        # Créer la série de barres (QBarSeries) en utilisant uniquement filtered_time_data
        series = QBarSeries()
        series.setLabelsVisible(True)
        series.setLabelsPosition(QBarSeries.LabelsPosition.LabelsInsideEnd) 
        categories = set()

        for computer, data in filtered_time_data.items():
            if period in data:
                bar_set = QBarSet(computer)
                for key, value in data[period].items():
                    bar_set.append(round(value, 2))
                    categories.add(key)
                series.append(bar_set)

        # Construire le graphique (QChart)
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(f"Utilisation par {period.capitalize()} pour '{chosen_computer}'")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        # Configuration de l'axe X
        axis_x = QBarCategoryAxis()
        sorted_categories = sorted(categories)
        axis_x.append(sorted_categories)
        axis_x.setTitleText("Date")
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

       # Configuration de l'axe Y
        axis_y = QValueAxis()
        axis_y.setTitleText("Utilisation (en heures)")
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        # Créer la vue du graphique
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Ajuster la taille du chart_view en fonction du nombre de catégories
        chart_view.setMinimumWidth(max(800, 80 * len(categories)))
        chart_view.setMinimumHeight(600)

        # QScrollArea pour un éventuel défilement horizontal
        scroll_area = QScrollArea()
        scroll_area.setWidget(chart_view)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Vide l'ancien contenu du QFrame usageGraphInside et y insérer le nouveau chart
        if self.usageGraphInside.layout() is None:
            layout = QVBoxLayout()
            self.usageGraphInside.setLayout(layout)
        else:
            layout = self.usageGraphInside.layout()
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        layout.addWidget(scroll_area)
        self.usageGraphInside.show()


    
    
    
    
    
    
    
    
    
    
    def search_in_computers(self):
        # Récupère tous les noms d'ordinateurs dans leur format d'origine
        all_computers = self.db_manager.fetch_all_computers()
        
        # Récupère la requête et la met en minuscules pour la comparaison
        query = self.lineComputer.text().lower()
        
        # Filtre les ordinateurs en comparant la version en minuscule du nom original avec la requête
        filtered_computers = [computer for computer in all_computers if query in computer.lower()]
        
        # Convertit les résultats filtrés en majuscules pour l'affichage
        filtered_computers_upper = [computer.upper() for computer in filtered_computers]
        
        # Met à jour le modèle du QCompleter
        self.completer.setModel(QStringListModel(filtered_computers_upper))
        
        # Vide le modèle actuel
        self.model.removeRows(0, self.model.rowCount())
        
        # Remplit le modèle avec les résultats en majuscules
        for computer in filtered_computers_upper:
            item = QStandardItem(computer)
            self.model.appendRow(item)


    def search_in_rooms(self):
        # Fetch all room names
        all_rooms = self.db_manager.group_computers_by_room().keys()
        
        # Get the query and convert it to lowercase for comparison
        query = self.lineEditRoom.text().lower()
        
        # Filter rooms by checking if the query is a substring of the room name
        filtered_rooms = [room for room in all_rooms if query in room.lower()]
        
        # Convert filtered results to uppercase for display
        filtered_rooms_upper = [room.upper() for room in filtered_rooms]
        
        # Update the completer model
        self.completer.setModel(QStringListModel(filtered_rooms_upper))
        
        # Clear the current model
        self.model.removeRows(0, self.model.rowCount())
        
        # Populate the model with filtered results in uppercase
        for room in filtered_rooms_upper:
            item = QStandardItem(room)
            self.model.appendRow(item)

        # If a single room is selected, display its monthly usage graph
        if len(filtered_rooms) == 1:
            self.lineEditRoom.setText(filtered_rooms[0])  # Set the exact room name
            self.monthly_usage_per_room_bar(filtered_rooms[0])



    def users_per_rooms_stats(self):
        self.last_value_sorted_chart_function = self.users_per_rooms_stats  # Store function reference
        if self.stackedWidget.currentWidget() == self.page_2:
            self.stackedWidget.setCurrentWidget(self.page)
        # Fetch all data
        users_per_room = self.db_manager.fetch_users_per_rooms_stats()

        # Sort all data by user count in descending order
        sorted_users_per_room = dict(sorted(
            users_per_room.items(),
            key=lambda item: item[1],
            reverse=self.sort_descending  # Use the state variable
        ))

        # Apply limit to sorted data
        limited_sorted_data = self.db_manager.fetch_limited_data(sorted_users_per_room)

        # Create QBarSet and categories using limited and sorted data
        bar_set = QBarSet("Utilisateurs par salle")
        categories = []
        for room, count in reversed(list(limited_sorted_data.items())):
            bar_set.append(count)
            categories.append(room)

        # Crée une série pour le graphique en barres horizontales
        series = QHorizontalBarSeries()
        series.append(bar_set)
        series.setLabelsVisible(True)
        series.setLabelsPosition(QHorizontalBarSeries.LabelsPosition.LabelsInsideEnd)

        # Crée un graphique et y ajoute la série
        chart = QChart()
        chart.addSeries(series)
        sort_order_text = "décroissant" if self.sort_descending else "croissant"
        chart.setTitle(f"Nombre d'Utilisateurs par salle (Ordre {sort_order_text})")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        # Définir la police du titre pour être plus gros et en gras
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        chart.setTitleFont(title_font)

        # Définir les axes
        axis_x = QValueAxis()
        axis_x.setTitleText("Nombre d'utilisateurs")
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QBarCategoryAxis()
        axis_y.append(categories)
        axis_y.setTitleText("Salles")
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        # Crée la vue du graphique
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Ajuster la taille du chart_view en fonction du nombre de catégories
        chart_view.setMinimumHeight(50 * len(categories))
        chart_view.setMinimumWidth(800)

        # Crée un QScrollArea pour permettre le défilement vertical
        scroll_area = QScrollArea()
        scroll_area.setWidget(chart_view)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        # Récupère ou crée le layout pour le QFrame ShowGraph
        if self.ShowGraph.layout() is None:
            layout = QVBoxLayout()
            self.ShowGraph.setLayout(layout)
        else:
            layout = self.ShowGraph.layout()
            # Vider le layout existant
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        # Ajoute le scroll_area dans le layout du QFrame
        layout.addWidget(scroll_area)
        self.ShowGraph.show()

    def percentage_per_rooms_stats(self):
        self.last_value_sorted_chart_function = self.percentage_per_rooms_stats  # Store function reference
        if self.stackedWidget.currentWidget() == self.page_2:
            self.stackedWidget.setCurrentWidget(self.page)
        
        # Fetch total usage time per room
        time_per_room = self.db_manager.fetch_time_per_rooms_stats()

        # Calculate total usage time across all rooms
        total_time = sum(time_per_room.values())

        # Calculate percentage usage for each room
        percentage_per_room = {room: (time / total_time) * 100 for room, time in time_per_room.items()}

        # Sort rooms by percentage in descending order
        sorted_percentage_per_room = dict(sorted(
            percentage_per_room.items(),
            key=lambda item: item[1],
            reverse=self.sort_descending  # Use the state variable
        ))

        limited_sorted_data = self.db_manager.fetch_limited_data(sorted_percentage_per_room)

        # Create QBarSet and categories using sorted data
        bar_set = QBarSet("Pourcentage d'utilisation")
        categories = []
        for room, percentage in reversed(list(limited_sorted_data.items())):
            bar_set.append(round(percentage, 2))
            categories.append(room)

        # Create a horizontal bar series
        series = QHorizontalBarSeries()
        series.append(bar_set)
        series.setLabelsVisible(True)
        series.setLabelsPosition(QHorizontalBarSeries.LabelsPosition.LabelsInsideEnd)
        series.setLabelsFormat("@value%")

        # Create a chart and add the series
        chart = QChart()
        chart.addSeries(series)
        sort_order_text = "décroissant" if self.sort_descending else "croissant"
        chart.setTitle(f"Pourcentage d'utilisation des salles (Ordre {sort_order_text})")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        # Set title font
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        chart.setTitleFont(title_font)

        # Define axes
        axis_x = QValueAxis()
        axis_x.setTitleText("Pourcentage d'utilisation")
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QBarCategoryAxis()
        axis_y.append(categories)
        axis_y.setTitleText("Salles")
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        # Create the chart view
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Adjust the chart view size
        chart_view.setMinimumHeight(50 * len(categories))
        chart_view.setMinimumWidth(800)

        # Create a QScrollArea for vertical scrolling
        scroll_area = QScrollArea()
        scroll_area.setWidget(chart_view)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        # Clear the old content of the QFrame ShowGraph and insert the new chart
        if self.ShowGraph.layout() is None:
            layout = QVBoxLayout()
            self.ShowGraph.setLayout(layout)
        else:
            layout = self.ShowGraph.layout()
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        layout.addWidget(scroll_area)
        self.ShowGraph.show()

    def time_per_rooms_stats(self):
        self.last_value_sorted_chart_function = self.time_per_rooms_stats  # Store function reference
        if self.stackedWidget.currentWidget() == self.page_2:
            self.stackedWidget.setCurrentWidget(self.page)
        # Fetch all data
        time_per_room = self.db_manager.fetch_time_per_rooms_stats()

        # Sort all data by total time in descending order
        sorted_time_per_room = dict(sorted(
            time_per_room.items(),
            key=lambda item: item[1],
            reverse=self.sort_descending  # Use the state variable
        ))

        # Apply limit to sorted data
        limited_sorted_data = self.db_manager.fetch_limited_data(sorted_time_per_room)

        # Create QBarSet and categories using limited and sorted data
        bar_set = QBarSet("Temps d'utilisation par salles (en heures)")
        categories = []
        for room, total_time in reversed(list(limited_sorted_data.items())):
            bar_set.append(round(total_time, 2))
            categories.append(room)

        # Crée une série pour le graphique en barres horizontales
        series = QHorizontalBarSeries()
        series.append(bar_set)
        series.setLabelsVisible(True)
        series.setLabelsPosition(QHorizontalBarSeries.LabelsPosition.LabelsInsideEnd)

        # Crée un graphique et y ajoute la série
        chart = QChart()
        chart.addSeries(series)
        sort_order_text = "décroissant" if self.sort_descending else "croissant"
        chart.setTitle(f"Temps d'utilisation total par salle (Ordre {sort_order_text}, Heures)")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        # Définir la police du titre pour être plus gros et en gras
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        chart.setTitleFont(title_font)

        # Définir les axes
        axis_x = QValueAxis()
        axis_x.setTitleText("Temps d'utilisation total (en heures)")
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QBarCategoryAxis()
        axis_y.append(categories)
        axis_y.setTitleText("Salles")
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        # Crée la vue du graphique
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Ajuster la taille du chart_view en fonction du nombre de catégories
        chart_view.setMinimumHeight(50 * len(categories))
        chart_view.setMinimumWidth(800)

        # Crée un QScrollArea pour permettre le défilement vertical
        scroll_area = QScrollArea()
        scroll_area.setWidget(chart_view)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        # Récupère ou crée le layout pour le QFrame ShowGraph
        if self.ShowGraph.layout() is None:
            layout = QVBoxLayout()
            self.ShowGraph.setLayout(layout)
        else:
            layout = self.ShowGraph.layout()
            # Vider le layout existant
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        # Ajoute le scroll_area dans le layout du QFrame
        layout.addWidget(scroll_area)
        self.ShowGraph.show()






    def monthly_usage_per_room_bar(self):
        self.last_value_sorted_chart_function = None  # Clear function reference (not value-sorted)
        if self.stackedWidget.currentWidget() == self.page_2:
            self.stackedWidget.setCurrentWidget(self.page)
        
        # Check if a room is selected
        selected_room = self.lineEditRoom.text().strip()
        if not selected_room:
            return  # Do nothing if no room is selected

        # Fetch data from DBManager
        monthly_usage_data = self.db_manager.fetch_monthly_usage_per_room()

        # Filter data for the selected room
        if selected_room not in monthly_usage_data:
            return  # Do nothing if the selected room has no data
        monthly_usage_data = {selected_room: monthly_usage_data[selected_room]}

        # Prepare data for the graph
        categories = set()  # Contains all months
        series = QBarSeries()

        for room, usage_data in monthly_usage_data.items():
            bar_set = QBarSet(room)
            for month, hours in usage_data.items():
                bar_set.append(round(hours, 2))  # Limit hours to 2 decimal places
                categories.add(month)
            series.append(bar_set)

        # Enable labels to display the number of hours inside the bars
        series.setLabelsVisible(True)
        series.setLabelsPosition(QBarSeries.LabelsPosition.LabelsInsideEnd)

        # Sort categories (months) chronologically
        sorted_categories = sorted(categories)

        # Create a chart and add the series
        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(f"Temps d'utilisation par mois de - {selected_room} (en heures)")
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)

        # Define axes
        axis_x = QBarCategoryAxis()
        axis_x.append(sorted_categories)
        axis_x.setTitleText("Mois")
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        axis_y.setTitleText("Temps d'utilisation (en heures)")
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        # Create the chart view
        chart_view = QChartView(chart)
        chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Adjust the chart view size
        chart_view.setMinimumWidth(100 * len(sorted_categories))
        chart_view.setMinimumHeight(600)

        # Create a QScrollArea for horizontal scrolling
        scroll_area = QScrollArea()
        scroll_area.setWidget(chart_view)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Clear the old content of the QFrame ShowGraph and insert the new chart
        if self.ShowGraph.layout() is None:
            layout = QVBoxLayout()
            self.ShowGraph.setLayout(layout)
        else:
            layout = self.ShowGraph.layout()
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()

        layout.addWidget(scroll_area)
        self.ShowGraph.show()

    def show_line_edit_for_room_selection(self):
        # Show the lineEditRoom and configure the completer
        self.lineEditRoom.setVisible(True)
        self.lineEditRoom.clear()  # Clear previous content

        # Configure the completer with room names
        all_rooms = self.db_manager.group_computers_by_room().keys()
        self.completer.setModel(QStringListModel(list(all_rooms)))
        self.lineEditRoom.setCompleter(self.completer)

    def inverse_order(self):
        # Toggle the sort direction and redraw the last value-sorted chart.
        if self.last_value_sorted_chart_function:
            self.sort_descending = not self.sort_descending  # Toggle sort order
            self.last_value_sorted_chart_function()  # Redraw the chart
        else:
            QMessageBox.warning(self, "Action impossible",
                                "Veuillez d'abord générer un graphique triable avant d'inverser l'ordre.")

    def set_limit_and_refresh(self, limit):
        self.db_manager.set_limit(limit)
        if self.last_value_sorted_chart_function:
            self.last_value_sorted_chart_function()  # Refresh the last sortable chart




















   
    
    def _get_current_chart_view(self):
        # Cette méthode détermine quel graphique est actuellement affiché et retourne le QFrame et la QChartView correspondants.
        target_frame = None
        chart_view = None

        # Détermine quel conteneur (page) est actif
        if self.stackedWidget.currentWidget() == self.page:
            target_frame = self.ShowGraph
        elif self.stackedWidget.currentWidget() == self.page_2:
            target_frame = self.usageGraphInside
        else:
            return None, None # Aucune page pertinente active

        # Trouve le QChartView dans le layout du conteneur
        layout = target_frame.layout()
        if layout and layout.count() > 0:
            # Suppose que le graphique est dans un QScrollArea qui est le premier widget
            scroll_area = layout.itemAt(0).widget()
            if isinstance(scroll_area, QScrollArea):
                widget_inside = scroll_area.widget()
                if isinstance(widget_inside, QChartView):
                    chart_view = widget_inside # C'est le widget que nous voulons

        return target_frame, chart_view # Retourne le conteneur et la vue du graphique

























    def export_chart(self):
        # Déterminer quel graphique est actuellement visible
        target_frame, chart_view = self._get_current_chart_view()

        if not chart_view:
            QMessageBox.warning(self, "Erreur", "Aucun graphique visible à exporter.")
            return

        # Adapter la taille selon le type de graphique
        size = chart_view.size()
        min_export_width, min_export_height = 800, 600
        size.setWidth(max(size.width(), min_export_width))
        size.setHeight(max(size.height(), min_export_height))

        # Demander le chemin de sauvegarde
        file_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Exporter le graphique",
            "",
            "PNG (*.png);;SVG (*.svg);;PDF (*.pdf)"
        )

        if not file_path:
            return

        # Ajouter l'extension si nécessaire
        if selected_filter == "PNG (*.png)" and not file_path.lower().endswith(".png"):
            file_path += ".png"
        elif selected_filter == "SVG (*.svg)" and not file_path.lower().endswith(".svg"):
            file_path += ".svg"
        elif selected_filter == "PDF (*.pdf)" and not file_path.lower().endswith(".pdf"):
            file_path += ".pdf"

        # Exporter selon le format
        try:
            if file_path.lower().endswith(".svg"):
                generator = QSvgGenerator()
                generator.setFileName(file_path)
                generator.setSize(size)
                generator.setViewBox(QRect(0, 0, size.width(), size.height()))
                painter = QPainter(generator)
                chart_view.render(painter)
                painter.end()

            elif file_path.lower().endswith(".pdf"):
                printer = QPrinter(QPrinter.PrinterMode.HighResolution)
                printer.setOutputFileName(file_path)
                printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
                printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
                printer.setPageOrientation(
                    QPageLayout.Orientation.Landscape if size.width() > size.height() else QPageLayout.Orientation.Portrait
                )
                painter = QPainter(printer)
                chart_view.render(painter)
                painter.end()

            elif file_path.lower().endswith(".png"):
                image = QImage(size, QImage.Format.Format_ARGB32)
                image.fill(Qt.GlobalColor.white)
                painter = QPainter(image)
                chart_view.render(painter)
                painter.end()
                image.save(file_path)

            QMessageBox.information(self, "Exportation réussie", f"Graphique exporté vers {file_path}.")
        except Exception as e:
            QMessageBox.critical(self, "Erreur d'exportation", f"Une erreur s'est produite : {e}")





    # Fonction pour imprimer le graphique
    def print_chart(self):
        """ Gère l'aperçu et l'impression du graphique visible. """
        # 1. Obtenir la vue du graphique actuellement affichée
        target_frame, chart_view = self._get_current_chart_view()

        if not chart_view:
            QMessageBox.warning(self, "Erreur", "Aucun graphique visible à imprimer.")
            return

        # 2. Créer un objet QPrinter (sera configuré par le dialogue d'aperçu)
        # Note: La résolution est importante pour la qualité de l'aperçu et de l'impression
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)

        # 3. Créer le dialogue d'aperçu avant impression
        # On passe l'objet printer et la fenêtre parente (self)
        preview_dialog = QPrintPreviewDialog(printer, self)
        preview_dialog.setWindowTitle("Aperçu avant impression")

        #  Connecter le signal paintRequested à une méthode qui fera le rendu
        preview_dialog.paintRequested.connect(
            lambda p: self._handle_paint_request(p, chart_view)
        )

        # 5. Afficher le dialogue d'aperçu
        if preview_dialog.exec() == QPrintPreviewDialog.DialogCode.Accepted:
            # L'utilisateur a cliqué sur l'icône Imprimer dans l'aperçu
            QMessageBox.information(self, "Impression", "Le graphique a été envoyé à l'imprimante.")
            # L'impression réelle a déjà été gérée via le signal paintRequested
        else:
            QMessageBox.information(self, "Impression annulée", "L'impression a été annulée.")


    def _handle_paint_request(self, printer: QPrinter, chart_view: QChartView):
        # Méthode appelée par QPrintPreviewDialog pour dessiner le contenu. 
        try:
            # Créer un painter pour dessiner sur l'imprimante fournie
            painter = QPainter()
            if painter.begin(printer):
                try:
                    # Obtenir le viewport (zone d'impression) du painter (retourne un QRect)
                    viewport_rect = painter.viewport()

                    # Convertir le QRect du viewport en QRectF pour la méthode render
                    target_rect_f = QRectF(viewport_rect) 

                    # Obtenir le rectangle source du widget graphique (QRect est OK pour source)
                    source_rect = chart_view.rect()

                    # Rendre le graphique en utilisant le QRectF pour la cible
                    chart_view.render(painter, target=target_rect_f, source=source_rect, mode=Qt.AspectRatioMode.KeepAspectRatio) # <<<--- Utiliser target_rect_f
                    # --- Fin de la logique de mise à l'échelle ---
                finally:
                    # Toujours terminer le painter
                    painter.end()
            else:
                # Ne pas afficher de QMessageBox ici car cette méthode peut être appelée plusieurs fois
                print("Erreur: Impossible de démarrer le QPainter sur l'imprimante pour l'aperçu/impression.")

        except Exception as e:
            # Éviter les QMessageBox répétitifs en cas d'erreur lors du rendu de l'aperçu
            print(f"Erreur lors du rendu pour l'aperçu/impression : {e}")