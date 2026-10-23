"""Profils des rencontres dont les règles particulières ont été contrôlées.

Une liste de groupes décrit des adversaires simultanés. Les groupes se succèdent,
mais le joueur change librement de cible offensive entre les assauts d’un groupe.
Les §§29/317 restent exclus tant que la source est ambiguë.
Le profil de l’Anguille (§186) a été confirmé par l’utilisateur.
"""

def enemy(name, skill, stamina):
    return {'name':name, 'skill':skill, 'stamina':stamina}


def successive(identity, victory, enemies, *, escape=None):
    """Décrire un adversaire par groupe, uniquement pour les successions explicites."""
    profile = {'identity':identity, 'victory_target':victory,
               'groups':[[enemy(*spec)] for spec in enemies]}
    if escape is not None:
        profile['escape_target'] = escape
    return profile


HUNTERS = [[enemy('Chien de chasse',7,6)],
           [enemy('Chien de chasse A',6,6),enemy('Chien de chasse B',5,6)],
           [enemy('Dernier chien',6,5),enemy('Homme masqué',8,7)]]
COMBATS = {
    7: successive('killer_bees',23,[('Premier essaim d’Abeilles Tueuses',7,3),
                                   ('Deuxième essaim d’Abeilles Tueuses',8,4),('Troisième essaim d’Abeilles Tueuses',7,4)]),
    9: successive('caged_goblin',176,[('Gobelin',5,4)]),
    117: successive('caged_goblin',232,[('Gobelin',5,4)]),
    15: successive('stinging_worm',217,[('Ver Piqueur',8,7)]),
    43: successive('woodsmen',50,[('Premier Homme des Bois',7,5),('Deuxième Homme des Bois',6,4)],escape=188),
    79: successive('tree_vampires',386,[('Premier Vampire',5,5),('Deuxième Vampire',6,5),('Troisième Vampire',5,7)]),
    118: successive('wild_boar',174,[('Sanglier Sauvage',6,5)]),
    128: successive('barbarian',272,[('Barbare',9,7)]),
    153: successive('cat_woman',202,[('Femme Féline',8,5)],escape=355),
    167: successive('wyvern',305,[('Vouivre Volante',10,11)]),
    181: successive('fish_man',162,[('Homme-Poisson',7,6)]),
    203: successive('shape_changer',373,[('Changeur de Forme',10,10)]),
    286: successive('shape_changer',373,[('Changeur de Forme',10,10)]),
    212: successive('warrior_clones',321,[('Premier Guerrier Clone',5,5),('Deuxième Guerrier Clone',6,4),
                                        ('Troisième Guerrier Clone',5,6),('Quatrième Guerrier Clone',6,5)],escape=107),
    241: successive('bear',219,[('Ours',7,8)]),
    265: successive('forest_giant',356,[('Géant des Forêts',9,9)]),
    290: successive('ogre',385,[('Ogre',8,12)],escape=358),
    298: successive('giant_spider',140,[('Araignée Géante',7,8)]),
    303: successive('pterodactyl',247,[('Ptérodactyle',7,8)]),
    330: successive('wolves',116,[('Premier Loup',7,8),('Deuxième Loup',7,7),('Troisième Loup',7,9)]),
    347: successive('dwarf',363,[('Nain',8,5)]),
    310: {'groups':[[enemy('Troll des Cavernes',8,9)]], 'victory_target':101,'identity':'cave_troll'},
    231: {'groups':[[enemy('Premier Faucon de la Mort',4,4)],
                    [enemy('Deuxième Faucon de la Mort',4,3)],
                    [enemy('Troisième Faucon de la Mort',5,4)]],
          'victory_target':224,'escape_target':332,'identity':'death_hawks'},
    186: {'groups':[[enemy('Anguille Carnivore',5,4)]], 'victory_target':131,'identity':'carnivorous_eel'},
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
