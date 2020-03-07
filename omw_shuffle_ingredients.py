#!/usr/bin/env python3

from struct import pack, unpack
from datetime import date
from pathlib import Path
from random import shuffle
import os.path
import argparse
import sys
import re


configFilename = 'openmw.cfg'
configPaths = { 'linux':   '~/.config/openmw',
                'freebsd': '~/.config/openmw',
                'darwin':  '~/Library/Preferences/openmw' }

modPaths = { 'linux':   '~/.local/share/openmw/data',
             'freebsd': '~/.local/share/openmw/data',
             'darwin':  '~/Library/Application Support/openmw/data' }
             

def packLong(i):
    # little-endian, "standard" 4-bytes (old 32-bit systems)
    return pack('<l', i)

def packFloat(i):
    return pack('<f', i)

def packString(s):
    return bytes(s, 'ascii')

def packPaddedString(s, l):
    bs = bytes(s, 'ascii')
    if len(bs) > l:
        # still need to null-terminate
        return bs[:(l-1)] + bytes(1)
    else:
        return bs + bytes(l - len(bs))

def parseString(ba):
    i = ba.find(0)
    return ba[:i].decode(encoding='ascii', errors='ignore')

def parseNum(ba):
    return int.from_bytes(ba, 'little', signed=True)

def parseFloat(ba):
    return unpack('f', ba)[0]

def parseTES3(rec):
    tesrec = {}
    sr = rec['subrecords']
    tesrec['version'] = parseFloat(sr[0]['data'][0:4])
    tesrec['filetype'] = parseNum(sr[0]['data'][4:8])
    tesrec['author'] = parseString(sr[0]['data'][8:40])
    tesrec['desc'] = parseString(sr[0]['data'][40:296])
    tesrec['numrecords'] = parseNum(sr[0]['data'][296:300])

    masters = []
    for i in range(1, len(sr), 2):
        mastfile = parseString(sr[i]['data'])
        mastsize = parseNum(sr[i+1]['data'])
        masters.append((mastfile, mastsize))

    tesrec['masters'] = masters
    return tesrec

def parseINGR(rec):
    ingrrec = {}
    srs = rec['subrecords']

    for sr in srs:
        if sr['type'] == 'NAME':
            ingrrec['id'] = parseString(sr['data'])
        elif sr['type'] == 'MODL':
            ingrrec['model'] = parseString(sr['data'])
        elif sr['type'] == 'FNAM':
            ingrrec['name'] = parseString(sr['data'])
        elif sr['type'] == 'ITEX':
            ingrrec['icon'] = parseString(sr['data'])
        elif sr['type'] == 'SCRI':
            ingrrec['script'] = parseString(sr['data'])
        elif sr['type'] == 'IRDT':
            attr_struct = sr['data']
            ingrrec['weight'] = parseFloat(attr_struct[0:4])
            ingrrec['value'] = parseNum(attr_struct[4:8])

            effect_tuples = []

            for i in range(0,4):
                effect = parseNum(attr_struct[(8+i*4):(12+i*4)])
                skill = parseNum(attr_struct[(24+i*4):(28+i*4)])
                attribute = parseNum(attr_struct[(40+i*4):(44+i*4)])

                effect_tuples.append((effect, skill, attribute))

            ingrrec['effects'] = effect_tuples
        else:
            print("unknown subrecord type '%s'" % sr['type'])
            ppRecord(rec)

    ingrrec['file'] = os.path.basename(rec['fullpath'])

    return ingrrec

def parseLEVC(rec):
    # we're not writing these back out, and we're only
    # interested in the ID and the list of items, so
    # disregard the other info

    levrec = {}
    sr = rec['subrecords']

    levrec['name'] = parseString(sr[0]['data'])

    if len(sr) > 3:
        listcount = parseNum(sr[3]['data'])
        listitems = []

        for i in range(0,listcount*2,2):
            itemid = parseString(sr[4+i]['data'])
            listitems.append(itemid)

        levrec['items'] = listitems
    else:
        levrec['items'] = []

    return levrec


def pullSubs(rec, subtype):
    return [ s for s in rec['subrecords'] if s['type'] == subtype ]

def readHeader(ba):
    header = {}
    header['type'] = ba[0:4].decode()
    header['length'] = int.from_bytes(ba[4:8], 'little')
    return header

def readSubRecord(ba):
    sr = {}
    sr['type'] = ba[0:4].decode()
    sr['length'] = int.from_bytes(ba[4:8], 'little')
    endbyte = 8 + sr['length']
    sr['data'] = ba[8:endbyte]
    return (sr, ba[endbyte:])

def readRecords(filename):
    fh = open(filename, 'rb')
    while True:
        headerba = fh.read(16)
        if headerba is None or len(headerba) < 16:
            return None

        record = {}
        header = readHeader(headerba)
        record['type'] = header['type']
        record['length'] = header['length']
        record['subrecords'] = []
        # stash the filename here (a bit hacky, but useful)
        record['fullpath'] = filename

        remains = fh.read(header['length'])

        while len(remains) > 0:
            (subrecord, restofbytes) = readSubRecord(remains)
            record['subrecords'].append(subrecord)
            remains = restofbytes

        yield record

def oldGetRecords(filename, rectype):
    return ( r for r in readRecords(filename) if r['type'] == rectype )

def getRecords(filename, rectypes):
    numtypes = len(rectypes)
    retval = [ [] for x in range(numtypes) ]
    for r in readRecords(filename):
        if r['type'] in rectypes:
            for i in range(numtypes):
                if r['type'] == rectypes[i]:
                    retval[i].append(r)
    return retval

def packStringSubRecord(lbl, strval):
    str_bs = packString(strval) + bytes(1)
    l = packLong(len(str_bs))
    return packString(lbl) + l + str_bs

def packIntSubRecord(lbl, num, numsize=4):
    # This is interesting. The 'pack' function from struct works fine like this:
    #
    # >>> pack('<l', 200)
    # b'\xc8\x00\x00\x00'
    #
    # but breaks if you make that format string a non-literal:
    #
    # >>> fs = '<l'
    # >>> pack(fs, 200)
    # Traceback (most recent call last):
    #   File "<stdin>", line 1, in <module>
    # struct.error: repeat count given without format specifier
    #
    # This is as of Python 3.5.2

    num_bs = b''
    if numsize == 4:
        # "standard" 4-byte longs, little-endian
        num_bs = pack('<l', num)
    elif numsize == 2:
        num_bs = pack('<h', num)
    elif numsize == 1:
        # don't think endian-ness matters for bytes, but consistency
        num_bs = pack('<b', num)
    elif numsize == 8:
        num_bs = pack('<q', num)

    return packString(lbl) + packLong(numsize) + num_bs

def packTES3(desc, numrecs, masters):
    start_bs = b'TES3'
    headerflags_bs = bytes(8)

    hedr_bs = b'HEDR' + packLong(300)
    version_bs = pack('<f', 1.0)

    # .esp == 0, .esm == 1, .ess == 32
    # suprisingly, .omwaddon == 0, also -- figured it would have its own
    ftype_bs = bytes(4)

    author_bs = packPaddedString('code copyright 2020, jmelesky', 32)
    desc_bs = packPaddedString(desc, 256)
    numrecs_bs = packLong(numrecs)

    masters_bs = b''
    for (m, s) in masters:
        masters_bs += packStringSubRecord('MAST', m)
        masters_bs += packIntSubRecord('DATA', s, 8)

    reclen = len(hedr_bs) + len(version_bs) + len(ftype_bs) + len(author_bs) +\
             len(desc_bs) + len(numrecs_bs) + len(masters_bs)
    reclen_bs = packLong(reclen)

    return start_bs + reclen_bs + headerflags_bs + \
        hedr_bs + version_bs + ftype_bs + author_bs + \
        desc_bs + numrecs_bs + masters_bs


def packINGR(rec):
    start_bs = b'INGR'

    headerflags_bs = bytes(8)

    id_bs = packStringSubRecord('NAME', rec['id'])
    modl_bs = packStringSubRecord('MODL', rec['model'])
    name_bs = packStringSubRecord('FNAM', rec['name'])

    irdt_bs = b'IRDT'
    irdt_bs += packLong(56) # this subrecord is always length 56
    irdt_bs += packFloat(rec['weight'])
    irdt_bs += packLong(rec['value'])
    for i in range(0,4):
        irdt_bs += packLong(rec['effects'][i][0])
    for i in range(0,4):
        irdt_bs += packLong(rec['effects'][i][1])
    for i in range(0,4):
        irdt_bs += packLong(rec['effects'][i][2])

    icon_bs = packStringSubRecord('ITEX', rec['icon'])
    script_bs = b''
    if 'script' in rec:
        script_bs = packStringSubRecord('SCRI', rec['script'])

    reclen = len(id_bs) + len(modl_bs) + len(name_bs) + \
        len(irdt_bs) + len(icon_bs) + len(script_bs)
    reclen_bs = packLong(reclen)

    return start_bs + reclen_bs + headerflags_bs + id_bs + \
        modl_bs + name_bs + irdt_bs + icon_bs + script_bs



def ppSubRecord(sr):
    if sr['type'] in ['NAME', 'INAM', 'CNAM', 'FNAM', 'MODL', 'TEXT', 'SCRI']:
        print("  %s, length %d, value '%s'" % (sr['type'], sr['length'], parseString(sr['data'])))
    elif sr['type'] in ['DATA', 'NNAM', 'INDX', 'INTV']:
        print("  %s, length %d, value '%s'" % (sr['type'], sr['length'], parseNum(sr['data'])))
    else:
        print("  %s, length %d" % (sr['type'], sr['length']))

def ppRecord(rec):
    print("%s, length %d" % (rec['type'], rec['length']))
    for sr in rec['subrecords']:
        ppSubRecord(sr)


def ppINGR(rec):
    print("Ingredient name: '%s'" % (rec['name']))
    print("  ID: '%s', file: '%s'" % (rec['id'], rec['file']))
    print("  Model: '%s', Icon: '%s'" % (rec['model'], rec['icon']))
    if 'script' in rec:
        print("  Script: '%s'" % (rec['script']))
    print("  %10s%10s%10s" % ("effect", "skill", "attribute"))
    for i in range(0,4):
        print("  %10d%10d%10d" % rec['effects'][i])

def ppTES3(rec):
    print("TES3 record, type %d, version %f" % (rec['filetype'], rec['version']))
    print("author: %s" % rec['author'])
    print("description: %s" % rec['desc'])

    for (mfile, msize) in rec['masters']:
        print("  master %s, size %d" % (mfile, msize))

    print()



def readCfg(cfg):
    # first, open the file and pull all 'data' and 'content' lines, in order

    data_dirs = []
    mods = []
    with open(cfg, 'r') as f:
        for l in f.readlines():
            # match of form "blah=blahblah"
            m = re.search(r'^(.*)=(.*)$', l)
            if m:
                varname = m.group(1).strip()
                # get rid of not only whitespace, but also surrounding quotes
                varvalue = m.group(2).strip().strip('\'"')
                if varname == 'data':
                    data_dirs.append(varvalue)
                elif varname == 'content':
                    mods.append(varvalue)

    # we've got the basenames of the mods, but not the full paths
    # and we have to search through the data_dirs to find them
    fp_mods = []
    for m in mods:
        for p in data_dirs:
            full_path = os.path.join(p, m)
            if os.path.exists(full_path):
                fp_mods.append(full_path)
                break

    print("Config file parsed...")

    return fp_mods


def dumpalchs(cfg):
    alchs = []
    fp_mods = readCfg(cfg)

    for f in fp_mods:
        [ ppTES3(parseTES3(x)) for x in oldGetRecords(f, 'TES3') ]

    for f in fp_mods:
        ingrs = [ parseINGR(x) for x in oldGetRecords(f, 'INGR') ]
        [ ppINGR(x) for x in ingrs ]



def shuffle_ingredients(ingredients):
    # Okay, here's what we're doing.
    #
    # First, let's take out all the ingredients that
    # don't have any effects. They're likely unused
    # or singular quest items.

    print("ingredients length: %s" % len(ingredients))

    final_ingredients = {}

    for ingr in ingredients.values():
        if ingr['effects'][0][0] < 0 \
           and ingr['effects'][1][0] < 0 \
           and ingr['effects'][2][0] < 0 \
           and ingr['effects'][3][0] < 0:
            final_ingredients[ingr['id']] = ingr

    print("final length: %s" % len(final_ingredients))

    for ingr in final_ingredients.values():
        del ingredients[ingr['id']]

    print("ingredients length: %s" % len(ingredients))

    # Next, we're going to build four lists, one
    # each for the first, second, third, and fourth
    # effects.
    #
    # Why?
    #
    # We want to maintain proportions of different
    # effects. For example, in Vanilla, Restore
    # Fatigue is common as a first effect, and only
    # shows up once as a second effect. Likewise,
    # in Vanilla, some effects only appear in one
    # ingredient. We want to keep those
    # characteristics

    effect_lists = [[],[],[],[]]
    for i in range(0,4):
        for ingr in ingredients.values():
            if ingr['effects'][i][0] > 0:
                effect_lists[i].append(ingr['effects'][i])

    # Next, we shuffle the ingredients, then go
    # through each effect, assigning it to an
    # ingredient. At the end, move any remaining
    # ingredients to the final list. Repeat
    # until we assign all four levels of effect

    ingr_array = [ x for x in ingredients.values() ]

    print("ingredients array length: %s" % len(ingr_array))

    for i in range(0,4):
        shuffle(ingr_array)
        total_effects = len(effect_lists[i])
        for j in range(0,total_effects):
            ingr_array[j]['effects'][i] = effect_lists[i][j]
        if len(ingr_array) > total_effects:
            for ingr in ingr_array[total_effects:]:
                final_ingredients[ingr['id']] = ingr
            del ingr_array[total_effects:]
        print("ingredients array length: %s" % len(ingr_array))
        print("final length: %s" % len(final_ingredients))


    # and then slap the rest in

    for ingr in ingr_array:
        final_ingredients[ingr['id']] = ingr

    print("final length: %s" % len(final_ingredients))


    print("first effects:  %s" % len(effect_lists[0]))
    print("second effects: %s" % len(effect_lists[1]))
    print("third effects:  %s" % len(effect_lists[2]))
    print("fourth effects: %s" % len(effect_lists[3]))

    print("total ingredients shuffled: %s" % len(final_ingredients))

    return final_ingredients



def main(cfg, outmoddir, outmod):
    fp_mods = readCfg(cfg)

    # first, let's grab the "raw" records from the files

    (rtes3, rlevc, ringr) = ([], [], [])
    for f in fp_mods:
        print("Parsing '%s' for relevant records" % f)
        (rtes3t, rlevct, ringrt) = getRecords(f, ('TES3', 'LEVC', 'INGR'))
        rtes3 += rtes3t
        rlevc += rlevct
        ringr += ringrt

    # next, parse the tes3 records so we can get a list
    # of master files required by all our mods

    tes3list = [ parseTES3(x) for x in rtes3 ]

    masters = {}
    for t in tes3list:
        for m in t['masters']:
            masters[m[0]] = m[1]

    master_list = [ (k,v) for (k,v) in masters.items() ]

    # parse the levc records -- we want to sort things
    # as food, if the appear in a food leveled list

    levclist = [ parseLEVC(x) for x in rlevc ]

    # get a list of items that appear in lists of "food"

    foodset = set()
    for ll in levclist:
        if 'food' in ll['name'] or 'Food' in ll['name']:
            for ingr in ll['items']:
                foodset.add(ingr)

    # now parse the ingredients entries.

    ilist = [ parseINGR(x) for x in ringr ]

    # we need to uniquify the list -- mods may alter
    # Vanilla ingredients by replacing them

    ingrs_by_id = {}
    for ingr in ilist:
        ingrs_by_id[ingr['id']] = ingr

    # look for ingredients that
    #   1- use the same models as each other
    #   2- have identical effects
    #
    # stash all but one of those ingredients so we
    # can maintain that consistency

    ingrs_by_model = {}
    for ingr in ingrs_by_id.values():
        if ingr['model'] in ingrs_by_model:
            ingrs_by_model['model'].append(ingr)
        else:
            ingrs_by_model['model'] = [ ingr ]

    dupe_ingrs = {}


    # now sort the ingredients into food and non-food

    foods_by_id = {}
    nonfoods_by_id = {}

    for ingr in ingrs_by_id.values():
        if ingr['id'] in foodset or 'food' in ingr['id'] \
           or 'Food' in ingr['id']:
            foods_by_id[ingr['id']] = ingr
        else:
            nonfoods_by_id[ingr['id']] = ingr

    print("total ingredient records: %s" % (len(ilist)))
    print("ingredients: %s" % (len(ingrs_by_id)))
    print("semi-identical ingredients: %s" % (len(dupe_ingrs)))
    print("total food: %s, total nonfood: %s" % (len(foods_by_id), len(nonfoods_by_id)))

    # now we build new lists with shuffled ingredient effects

    shuffled_foods = shuffle_ingredients(foods_by_id)
    shuffled_nonfoods = shuffle_ingredients(nonfoods_by_id)

    # now turn those ingredients back into INGR records
    #
    # along the way, build up the module
    # description for the new merged mod, out
    # of the names of mods that had ingredients

    ilist_bin = b''
    plugins = set()
    for x in shuffled_foods.values():
        ilist_bin += packINGR(x)
        plugins.add(x['file'])
    for x in shuffled_nonfoods.values():
        ilist_bin += packINGR(x)
        plugins.add(x['file'])

    moddesc = "Shuffled ingredients from: %s" % ', '.join(plugins)

    # finally, build the binary form of the
    # TES3 record, and write the whole thing
    # out to disk

    if not os.path.exists(outmoddir):
        p = Path(outmoddir)
        p.mkdir(parents=True)

    with open(outmod, 'wb') as f:
        f.write(packTES3(moddesc, len(shuffled_foods) +
                         len(shuffled_nonfoods), master_list))
        f.write(ilist_bin)

    # And give some hopefully-useful instructions

    modShortName = os.path.basename(outmod)
    print("\n\n****************************************")
    print(" Great! I think that worked. When you next start the OpenMW Launcher, look for a module named %s. Make sure of the following things:" % modShortName)
    print("    1. %s is at the bottom of the list. Drag it to the bottom if it's not. It needs to load last." % modShortName)
    print("    2. %s is checked (enabled)" % modShortName)
    print("    3. Any other OMW ingredient shuffler mods are *un*checked. Loading them might not cause problems, but probably will")
    print("\n")
    print(" Then, go ahead and start the game! All alchemy ingredients from all your mods should now have shuffled effects.")
    print("\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()

    parser.add_argument('-c', '--conffile', type = str, default = None,
                        action = 'store', required = False,
                        help = 'Conf file to use. Optional. By default, attempts to use the default conf file location.')

    parser.add_argument('-d', '--moddir', type = str, default = None,
                        action = 'store', required = False,
                        help = 'Directory to store the new module in. By default, attempts to use the default work directory for OpenMW-CS')

    parser.add_argument('-m', '--modname', type = str, default = None,
                        action = 'store', required = False,
                        help = 'Name of the new module to create. By default, this is "Shuffled Ingredients - <today\'s date>.omwaddon.')

    parser.add_argument('--dumpalchs', default = False,
                        action = 'store_true', required = False,
                        help = 'Instead of generating merged lists, dump all alchemy ingredients in the conf mods. Used for debugging')

    p = parser.parse_args()


    # determine the conf file to use
    confFile = ''
    if p.conffile:
        confFile = p.conffile
    else:
        pl = sys.platform
        if pl in configPaths:
            baseDir = os.path.expanduser(configPaths[pl])
            confFile = os.path.join(baseDir, configFilename)
        elif pl == 'win32':
            # this is ugly. first, imports that only work properly on windows
            from ctypes import *
            import ctypes.wintypes

            buf = create_unicode_buffer(ctypes.wintypes.MAX_PATH)

            # opaque arguments. they are, roughly, for our purposes:
            #   - an indicator of folder owner (0 == current user)
            #   - an id for the type of folder (5 == 'My Documents')
            #   - an indicator for user to call from (0 same as above)
            #   - a bunch of flags for different things
            #     (if you want, for example, to get the default path
            #      instead of the actual path, or whatnot)
            #     0 == current stuff
            #   - the variable to hold the return value

            windll.shell32.SHGetFolderPathW(0, 5, 0, 0, buf)

            # pull out the return value and construct the rest
            baseDir = os.path.join(buf.value, 'My Games', 'OpenMW')
            confFile = os.path.join(baseDir, configFilename)
        else:
            print("Sorry, I don't recognize the platform '%s'. You can try specifying the conf file using the '-c' flag." % p)
            sys.exit(1)

    baseModDir = ''
    if p.moddir:
        baseModDir = p.moddir
    else:
        pl = sys.platform
        if pl in configPaths:
            baseModDir = os.path.expanduser(modPaths[pl])
        elif pl == 'win32':
            # this is ugly in exactly the same ways as above.
            # see there for more information

            from ctypes import *
            import ctypes.wintypes

            buf = create_unicode_buffer(ctypes.wintypes.MAX_PATH)

            windll.shell32.SHGetFolderPathW(0, 5, 0, 0, buf)

            baseDir = os.path.join(buf.value, 'My Games', 'OpenMW')
            baseModDir = os.path.join(baseDir, 'data')
        else:
            print("Sorry, I don't recognize the platform '%s'. You can try specifying the conf file using the '-c' flag." % p)
            sys.exit(1)


    if not os.path.exists(confFile):
        print("Sorry, the conf file '%s' doesn't seem to exist." % confFile)
        sys.exit(1)

    modName = ''
    if p.modname:
        modName = p.modname
    else:
        modName = 'Shuffled Ingredients - %s.omwaddon' % date.today().strftime('%Y-%m-%d')

    modFullPath = os.path.join(baseModDir, modName)

    if p.dumpalchs:
        dumpalchs(confFile)
    else:
        main(confFile, baseModDir, modFullPath)





# regarding the windows path detection:
#
# "SHGetFolderPath" is deprecated in favor of "SHGetKnownFolderPath", but
# >>> windll.shell32.SHGetKnownFolderPath('{FDD39AD0-238F-46AF-ADB4-6C85480369C7}', 0, 0, buf2)
# -2147024894


