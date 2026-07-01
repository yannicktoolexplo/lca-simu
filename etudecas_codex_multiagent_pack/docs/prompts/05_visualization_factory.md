# Prompt Codex — FigureFactory générique

Tu es l’agent visualisation du repo `etudecas`.

Objectif : créer une `FigureFactory` générique qui génère les figures depuis une `visual_spec` YAML.

À faire :
- identifier les visualisations existantes ;
- extraire les paramètres en config ;
- créer `FigureFactory` ;
- supporter au minimum `trajectory_3d` et `time_series` ;
- ajouter un test qui vérifie que la figure est générée.

Contraintes :
- pas de dataset spécifique dans le code ;
- pas de colonnes codées en dur ;
- axes, titres, dimensions et sorties viennent de YAML.
