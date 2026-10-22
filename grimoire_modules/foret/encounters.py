"""Profils des rencontres dont les règles particulières ont été contrôlées.

Une liste de groupes décrit des adversaires simultanés. Les groupes se succèdent,
mais le joueur change librement de cible offensive entre les assauts d’un groupe.
Les §§29/317 et l’Anguille (§186) restent exclus tant que la source est ambiguë.
"""

def enemy(name, skill, stamina):
    return {'name':name, 'skill':skill, 'stamina':stamina}


HUNTERS = [[enemy('Chien de chasse',7,6)],
           [enemy('Chien de chasse A',6,6),enemy('Chien de chasse B',5,6)],
           [enemy('Dernier chien',6,5),enemy('Homme masqué',8,7)]]
COMBATS = {
    49: {'groups':[[enemy('Gremlin A',4,3)],[enemy('Gremlin B',3,2)]], 'victory_target':371,'identity':'low_gremlins'},
    71: {'groups':[[enemy('Chef Gremlin',5,5)]], 'victory_target':273,'identity':'gremlin_chief'},
    165: {'groups':[[enemy('Gremlin du tunnel',5,3)]], 'victory_target':242,'identity':'tunnel_gremlin'},
    193: {'groups':[[enemy('Gremlin de l’échelle',4,4)]], 'victory_target':110,'identity':'ladder_gremlin'},
    352: {'groups':[[enemy('Homme-Singe',8,7)]], 'victory_target':207,'escape_target':156,'identity':'ape_man'},
    96: {'groups':HUNTERS, 'victory_target':62, 'identity':'hunters'},
    276: {'groups':HUNTERS, 'victory_target':62, 'identity':'hunters'},
    104: {'groups':[[enemy('Femme bandit',8,6)],
                    [enemy('Bandit A — première paire',7,6),enemy('Bandit B — première paire',6,4)],
                    [enemy('Bandit A — deuxième paire',7,5),enemy('Bandit B — deuxième paire',5,6)]],
          'victory_target':311, 'identity':'bandits'},
    377: {'groups':[[enemy('Pygmée A',5,5),enemy('Pygmée B',5,6)]],
          'victory_target':205,'escape_target':92,'identity':'pygmies'},
    107: {'groups':[[enemy('Démon de Feu',10,10)]], 'victory_target':152, 'identity':'fire_demon'},
    227: {'groups':[[enemy('Goule',9,7)]], 'victory_target':312, 'identity':'ghoul'},
    285: {'groups':[[enemy('Loup-Garou',8,9)]], 'victory_target':388, 'identity':'werewolf'},
    84: {'groups':[[enemy('Créature des Rochers',8,11)]], 'victory_target':146,
         'escape_target':245,'escape_after_assaults':3,'identity':'rock_creature'},
    123: {'groups':[[enemy('Homme-Arbre — première branche',8,8)],
                    [enemy('Homme-Arbre — deuxième branche',8,8)]],
          'victory_target':27,'escape_target':234,'identity':'tree_man'},
}
