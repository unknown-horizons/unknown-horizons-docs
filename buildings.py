#!/usr/bin/env python3

import itertools
import operator
import os
import sys

DOCS_PATH = os.path.dirname(os.path.abspath(__file__))

from init import db
from horizons.constants import BUILDINGS, TIER, UNITS
from horizons.entities import Entities
from horizons.util.loaders.actionsetloader import ActionSetLoader

ActionSetLoader._find_action_sets('content/')

settler_names = dict(db('SELECT level, name FROM tier'))
unit_sets = dict((u.id, u.action_sets) for u in Entities.units.values())
SHIP_THUMBNAIL = 'content/gui/icons/units/thumbnails/{type_id}.png'
RES_PATH = 'content/gui/icons/resources/32/{id:03d}.png'

global gh, used_res_ids
gh = 'https://github.com/unknown-horizons/unknown-horizons/raw/master/'
#gh = 'file://localhost/{path}/'.format(path=os.path.abspath(sys.argv[1]))
used_res_ids = set()
footer = set()

header = """
Buildings Overview
==================

""".lstrip()

all_sets = ActionSetLoader.action_sets


def get_image_url(building, tier=None):
	if tier is None:
		tier = 0
        #TODO: Below code is extremely ugly. Are the values and/or keys expected to 
        # contain more elements than 1 (index 0)?
		sets = all_sets[list(list(building.action_sets.values())[0].keys())[0]]
	else:
		building_sets = list(building.action_sets[tier].keys())
		sets = all_sets[building_sets[0]]
		if building.id == 3 and tier == TIER.CITIZENS:
			# Overwrite since first image has weight 0
			sets = all_sets[building_sets[1]]

	for key in ("idle_full", "idle", "work", "abc", "abd"):
		if sets.get(key) is not None:
			path = sets.get(key)
			break
	
	path = next(iter(path[45].keys()))
	line = '.. |b{tier:1d}x{id:03d}| image:: {path}\n'.format(tier=tier, id=building.id, path=gh+path)
	footer.add(line)
	return '|b{tier:1d}x{id:03d}|'.format(tier=tier, id=building.id)

def sphinx_section(text, level):
	return '%s\n%s\n' % (text, level * len(text))

def get_res_icon_path(res_id):
	if res_id >= UNITS.DIFFERENCE_BUILDING_UNIT_ID: # produced resource is a unit in disguise
		return gh + SHIP_THUMBNAIL.format(type_id=res_id)
	elif res_id < 0 or res_id > 900:
		return # no resource but still present in building property table (e.g. x, y size)
	return gh + RES_PATH.format(id=res_id)

def get_building_name(b, tier):
	if hasattr(b, '_level_specific_names'):
		return b._level_specific_names.get(tier, next(iter(b._level_specific_names.keys())))
	else:
		return b.name

def get_building_table(b, tier):
	ret = sphinx_section(get_building_name(b, tier), '`')
	if b.tooltip_text:
		if b.tooltip_text.startswith('_ '):
			b.tooltip_text = b.tooltip_text[2:]
		ret += b.tooltip_text + '\n\n'
	costs = get_building_cost_list(b)
	table_border = '+----------+-' + '-' * len(costs[0]) + '-+\n'
	ret += table_border
	ret += '| ' + get_image_url(b, tier) + ' | ' + costs[0] + ' |\n'
	for line in costs[1:]:
		ret += '|          | ' + line + ' |\n'
	production = get_production_output(b)
	if production:
		ret += '|          | ' + ' '+production + ' ' * (len(costs[0]) - 16) + ' |\n'
	# 16 is the length of the string ' |produces_b???|'. the additional space is required because
	# else the table would try to use the | replacement operator as alignment and thus break syntax.

	ret += table_border
	return ret + '\n'

def get_building_cost_list(building):
	for r in building.costs:
		used_res_ids.add(r)
	building.costs[-99] = building.running_costs or 0
	building.costs[-98] = building.running_costs_inactive or 0
	building.costs[980] = building.size[0]
	building.costs[981] = building.size[1]
	costs = sorted(building.costs.items())
	column_separator = '+-' + '-+-'.join('------' for (_, _) in costs) + '-+'
	ret = []
	ret.append(column_separator)
	ret.append('| ' + ' | '.join('|r%03d|' % r for (r, _) in costs) + ' |')
	ret.append(column_separator)
	ret.append('| ' + ' | '.join( '%6d'    % a for (_, a) in costs) + ' |')
	ret.append(column_separator)
	return ret

def get_production_output(building):
	ret = ''
	if hasattr(building, 'component_templates'):
		produced_res = set()
		for component in building.component_templates:
			for k, v in component.items():
				if 'ProducerComponent' in k:
					for _, line in component[k]['productionlines'].items():
						output = line.get('produces')
						if output:
							produced_res.add(output[0][0])
							used_res_ids.add(output[0][0])
					if produced_res:
						ret      += '.. |produces_b{bid:03d}| replace::\n'.format(bid=building.id)
						ret      += ' '*29 + 'Produces:\n'
						for id in produced_res:
							ret += ' '*29 + '|r{id:03d}|\n'.format(id=id)
	if ret:
		footer.add(ret)
		return '|produces_b{bid:03d}|'.format(bid=building.id)

def generate_overview(buildings):
	# Insert new pseudo-buildings for each tier upgrade to show all graphics.
	# (Trail, SAILORS) will also spawn (Trail, PIONEERS) and so on.
	# The correct name, if available, is then written during table generation.
	buildings = [(b, tier) for b in buildings for tier in b.action_sets]
	buildings.sort(key=operator.itemgetter(1))

	with open(os.path.join(DOCS_PATH, 'docs/buildings.rst'), 'w') as f:
		f.write(header)
		for level, buildings in itertools.groupby(buildings, key=operator.itemgetter(1)):
			level_name = settler_names[level]
			f.write(sphinx_section(level_name, "'"))
			for b, tier in buildings:
				f.write(get_building_table(b, tier))
		f.write('\n' * 3)

		# create replace rules for all required resource icons
		for id in used_res_ids:
			icon_path = get_res_icon_path(id)
			if icon_path is None:
				continue
			footer.add('.. |r{id:03d}| image:: {path}\n'.format(id=id, path=icon_path))
		footer.add('.. |r-99| image:: {path}\n'.format(path=gh+'content/gui/icons/resources/negative32.png'))
		footer.add('.. |r-98| image:: {path}\n'.format(path=gh+'content/gui/icons/resources/zzz32.png'))
		footer.add('.. |r980| replace:: x\n')
		footer.add('.. |r981| replace:: y\n')
		for line in sorted(footer):
			f.write(line)


def main():
	data = []
	for b in Entities.buildings.values():
		data.append(b)

	generate_overview(data)

    
if __name__ == '__main__':
	main()
