import numpy as np

# Implémentation simplifiée du modèle GM(1,1)
class GreyLib:
    """Bibliothèque de calcul pour le modèle Grey GM(1,1) simplifié (AGO et série Z)."""
    def __init__(self, alpha=0.5):
        # Coefficient alpha utilisé pour le calcul de la série Z (0.5 => moyenne, autre => IAGO)
        self.alpha = alpha

    def ago(self, patterns):
        """
        Calcule la série AGO (Accumulated Generation Output) à partir d'une liste de séries `patterns`.
        Retourne un tuple (ago_series, z_series).
        """
        ago_series = []
        z_series = []
        for p_index, pattern in enumerate(patterns):
            cumulative_sum = 0.0
            pattern_ago = []
            for x_index, x_value in enumerate(pattern):
                cumulative_sum += x_value
                pattern_ago.append(cumulative_sum)
                # Pour le premier pattern, calculer la valeur Z à partir du second point
                if p_index == 0 and x_index > 0:
                    z_val = self.alpha * cumulative_sum + self.alpha * pattern_ago[x_index - 1]
                    z_series.append(z_val)
            ago_series.append(pattern_ago)
        return ago_series, z_series

class GreyMath:
    """Outils de résolution mathématique (moindres carrés) pour le modèle Grey."""
    def solve_equations(self, equations, equals):
        """
        Résout un système d'équations linéaires par la méthode des moindres carrés.
        :param equations: matrice des coefficients (2D list)
        :param equals: vecteur des ordonnées (1D list)
        :return: solution approchée des équations (liste de coefficients)
        """
        # Calcul (B^T * B)^-1 * B^T * Yn
        B_T = np.array(equations).T
        square_matrix = np.dot(B_T, equations)
        B_T_y = np.dot(B_T, equals)
        solution = np.linalg.solve(square_matrix, B_T_y)
        return solution.tolist()

class GreyFactory:
    """Structure représentant les paramètres d'une série grise modélisée."""
    def __init__(self, name="", equation_value="", ranking=""):
        self.name = name
        self.equation_value = equation_value
        self.ranking = ranking

class GreyForecast:
    """Structure représentant un résultat de prévision dans le modèle GM(1,1)."""
    def __init__(self, tag="", k=0, original_value=0.0, forecast_value=0.0, error_rate=0.0, average_error_rate=0.0):
        self.tag = tag
        self.k = k
        self.original_value = original_value
        self.forecast_value = forecast_value
        self.error_rate = error_rate
        self.average_error_rate = average_error_rate

class GreyClass:
    """Classe de base du modèle Grey GM(1,1) simplifié."""
    _TAG_FORECAST_NEXT_MOMENT = "forecasted_next_moment"
    _TAG_FORECAST_HISTORY = "history"

    def __init__(self):
        self.tag = self.__class__.__name__
        self.patterns = []           # Ensemble des patterns (entrées) du modèle
        self.keys = []               # Étiquettes des patterns
        self.analyzed_results = []   # Résultats analysés (instances GreyFactory ou GreyForecast)
        self.influence_degrees = []  # Degrés d'influence de chaque paramètre
        self.grey_lib = GreyLib()
        self.grey_math = GreyMath()
        self.forecasted_outputs = [] # Valeurs prédites (après révision)

    def _add_outputs(self, outputs, pattern_key):
        """Ajoute une série de sorties (outputs) et sa clé associée au modèle."""
        self.patterns.insert(0, outputs)
        self.keys.append(pattern_key)

    def _add_patterns(self, patterns, pattern_key):
        """Ajoute une série d'entrées (patterns) et sa clé associée au modèle."""
        self.patterns.append(patterns)
        self.keys.append(pattern_key)

    def ago(self, patterns):
        """Calcule les séries AGO pour les `patterns` fournis en utilisant la GreyLib."""
        return self.grey_lib.ago(patterns)

    def remove_all_analysis(self):
        """Réinitialise les analyses précédentes du modèle."""
        self.analyzed_results = []
        self.influence_degrees = []
        # Supprimer les résultats de prévision antérieurs
        self.forecasted_outputs = []

    def print_self(self):
        """Affiche le nom de la classe (modèle Grey) dans la console."""
        print(f"{self.__class__.__name__!r}")

    def print_analyzed_results(self):
        """Affiche les résultats analysés pour chaque pattern sous forme textuelle."""
        self.print_self()
        for factory in self.analyzed_results:
            print(f"Pattern key: {factory.name!r}, grey value: {factory.equation_value!r}, ranking: {factory.ranking!r}")

    def print_influence_degrees(self):
        """Affiche l'ordre d'influence des paramètres."""
        self.print_self()
        ordered = " > ".join(self.influence_degrees)
        print(f"The keys of parameters their influence degrees (ordering): {ordered!r}")

    def print_forecasted_results(self):
        """Affiche les résultats de prévision stockés dans analyzed_results."""
        self.print_self()
        for forecast in self.analyzed_results:
            print(f"K = {forecast.k!r}")
            if forecast.tag == self._TAG_FORECAST_HISTORY:
                # Prévision rétrospective (historique)
                print(f"From revised value {forecast.original_value!r} to forecasted value is {forecast.forecast_value!r}")
                print(f"The error rate is {forecast.error_rate!r}")
            else:
                # Prévision des moments futurs
                print(f"Forecasted next moment value is {forecast.forecast_value!r}")
        if self.analyzed_results:
            last = self.analyzed_results[-1]
            print(f"The average error rate {last.average_error_rate!r}")

class GreyGM11(GreyClass):
    """Modèle Grey GM(1,1) simplifié pour la prévision."""
    def __init__(self):
        super(GreyGM11, self).__init__()
        self.stride = 1
        self.length = 4
        self.period = 1    # Nombre de pas futurs à prédire en continu (par défaut 1)
        self.convolution = False

    def add_pattern(self, pattern, pattern_key):
        """Ajoute une série de données (pattern) avec son étiquette au modèle GM(1,1)."""
        self._add_patterns(pattern, pattern_key)

    def add_output(self, output, output_key):
        """Ajoute une série de sortie (output) avec son étiquette au modèle GM(1,1)."""
        self._add_outputs(output, output_key)

    def __forecast(self, patterns, period=1):
        """
        Prévision interne basique (sans convolution) sur un nombre de périodes donné.
        Retourne une liste de GreyForecast.
        """
        forecasts = []
        # (Implémentation du calcul GM(1,1) simplifiée à ajouter)
        # ...
        return forecasts

    def __forecast_convolution(self, patterns, stride, length):
        """
        Prévision interne avec convolution sur plusieurs pas (multi-step forecasting).
        """
        convolutions = []
        # (Implémentation du calcul convolutionnel à ajouter)
        # ...
        return convolutions

    def forecast(self):
        """
        Lance la prévision à partir des patterns ajoutés au modèle.
        :return: Liste de GreyForecast (résultats de prévision) ou convolution selon configuration.
        """
        if self.convolution:
            return self.__forecast_convolution(self.patterns, self.stride, self.length)
        else:
            return self.__forecast(self.patterns, self.period)

    def continue_forecasting(self, last_forecasted_outputs=None):
        """
        Continue la prévision en réutilisant les dernières sorties prédites (utile pour forecast convolutionnel).
        :param last_forecasted_outputs: liste d'outputs prévus lors de la dernière prévision
        """
        if last_forecasted_outputs is None:
            last_forecasted_outputs = []
        self.forecasted_outputs.extend(last_forecasted_outputs)

    def clean_forecasted(self):
        """Réinitialise la liste des outputs prévus."""
        self.forecasted_outputs = []

    @property
    def last_moment(self):
        """Retourne la dernière valeur prédite (dernier GreyForecast enregistré)."""
        if not self.analyzed_results:
            return None
        return self.analyzed_results[-1].forecast_value

class GreyTheory:
    """Enveloppe simple pour utiliser le modèle Grey GM(1,1)."""
    def __init__(self):
        self.gm11 = GreyGM11()
