"""Real Lightroom acceptance using a procedural calibration fixture, never a user photo.

Pillow only creates the input fixture and measures Lightroom's exports; it never grades
or renders an output. Completed requests are persisted. Unknown outcomes stop the run.
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from bridge_client import send_command, wait_result


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    pending = path.with_suffix('.tmp')
    pending.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    pending.replace(path)


def fixture(path):
    """A chart, not generated photo content or a color-adjusted deliverable."""
    image = Image.new('RGB', (960,640))
    draw = ImageDraw.Draw(image)
    for x in range(960):
        level = round(255*x/959)
        draw.line((x,0,x,239), fill=(level,level,level))
    colors = [(190,70,60),(200,130,75),(200,190,70),(75,145,75),
              (65,155,160),(65,100,180),(120,75,160),(180,75,135)]
    for index,(r,g,b) in enumerate(colors):
        for y in range(240,600):
            factor = .25+.75*(y-240)/359
            draw.line((index*120,y,(index+1)*120-1,y), fill=tuple(round(v*factor) for v in (r,g,b)))
    draw.rectangle((0,600,959,639), fill=(32,32,32))
    draw.text((20,614),'PHOTO STYLE MATCH / LIGHTROOM NATIVE SDK VALIDATION / TEST CHART',fill=(220,220,220))
    image.save(path, quality=98, subsampling=0)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', required=True)
    parser.add_argument('--run-dir', required=True, type=Path)
    parser.add_argument('--state-dir', required=True, type=Path)
    args=parser.parse_args()
    root=args.run_dir.resolve()
    root.mkdir(parents=True,exist_ok=True)
    state_path=root/'validation.json'
    if state_path.exists():
        state=json.loads(state_path.read_text(encoding='utf-8'))
        if state['catalog']!=args.catalog:
            raise RuntimeError('Run catalog changed')
    else:
        path=root/'PhotoStyle-calibration.jpg'
        if path.exists():
            raise RuntimeError('Refusing to overwrite existing fixture')
        fixture(path)
        state={'catalog':args.catalog,'source_path':str(path),'source_sha256_before':digest(path),'steps':{}}
        save(state_path,state)
    path=state['source_path']

    def step(name, action, *, allow_rejection=False, **kwargs):
        stored=state['steps'].get(name)
        if stored and stored.get('status')=='outcome_unknown':
            stored=wait_result(args.state_dir,stored['id'],1)
            state['steps'][name]=stored; save(state_path,state)
        if not stored:
            print('Lightroom: '+name,flush=True)
            stored=send_command(action,catalog=args.catalog,path=path,state_dir=args.state_dir,timeout=45,**kwargs)
            state['steps'][name]=stored; save(state_path,state)
        if not stored.get('ok') and not (allow_rejection and 'status' not in stored):
            raise RuntimeError(json.dumps(stored,ensure_ascii=False))
        return stored

    master=step('import_fixture','import')['result']['photo']
    master_id=master['photo_id']
    baseline=step('read_master_before','read',photo_id=master_id)['result']['photo']
    copy=step('create_virtual_copy','copy',photo_id=master_id)['result']['photo']
    copy_id=copy['photo_id']
    before_export=step('export_before','export',photo_id=copy_id,output_dir=str(root/'before'))
    tone={'Exposure2012':0.65,'Contrast2012':18,'Highlights2012':-28,'Shadows2012':22,'Whites2012':-12,'Blacks2012':-8}
    first=step('apply_tone','apply',photo_id=copy_id,settings=tone,expected={k:copy['settings'][k] for k in tone})
    current=step('read_before_color','read',photo_id=copy_id)['result']['photo']['settings']
    color={'Vibrance':12,'Saturation':-8,'IncrementalTemperature':8,'IncrementalTint':-3,
           'HueAdjustmentOrange':-7,'SaturationAdjustmentYellow':-18,'LuminanceAdjustmentBlue':-12,
           'SplitToningShadowHue':210,'SplitToningShadowSaturation':12,
           'SplitToningHighlightHue':42,'SplitToningHighlightSaturation':8,'SplitToningBalance':8,
           'ColorGradeMidtoneHue':32,'ColorGradeMidtoneSat':6,'ColorGradeBlending':50}
    missing=set(color)-set(current)
    if missing:
        raise RuntimeError('Expected JPEG parameters absent: '+str(sorted(missing)))
    final=step('apply_color','apply',photo_id=copy_id,settings=color,expected={k:current[k] for k in color})
    readback=step('independent_readback','read',photo_id=copy_id)['result']['photo']
    for key,value in (tone|color).items():
        if abs(readback['settings'][key]-value)>0.0001:
            raise RuntimeError('Independent parameter readback mismatch: '+key)
    after_export=step('export_after','export',photo_id=copy_id,output_dir=str(root/'after'))
    rejected=step('reject_original_write','apply',photo_id=master_id,
                  settings={'Exposure2012':.1},expected={'Exposure2012':baseline['settings']['Exposure2012']},allow_rejection=True)
    if rejected['ok'] or 'originals' not in rejected.get('error',''):
        raise RuntimeError('Original protection check failed')
    source_after=step('read_master_after','read',photo_id=master_id)['result']['photo']
    if any(source_after['settings'].get(k)!=v for k,v in baseline['settings'].items()) or digest(path)!=state['source_sha256_before']:
        raise RuntimeError('Source changed')
    before_path=before_export['result']['files']['1']
    after_path=after_export['result']['files']['1']
    before=np.asarray(Image.open(before_path).convert('RGB'),dtype=np.float64)
    after=np.asarray(Image.open(after_path).convert('RGB'),dtype=np.float64)
    if before.shape!=after.shape:
        raise RuntimeError('Export dimensions changed')
    difference=float(np.mean(np.abs(after-before)))
    if difference<1:
        raise RuntimeError('Native exports do not show a substantial image change')
    state['acceptance']={'passed':True,'renderer':'Lightroom Classic','virtual_copy':readback,
        'verified_parameter_count':len(tone|color),'parameters_requested':tone|color,
        'source_develop_settings_unchanged':True,'source_sha256_unchanged':True,
        'original_write_rejected':True,'before_export':before_path,'after_export':after_path,
        'image_shape':list(before.shape),'mean_absolute_rgb_difference_8bit':difference,
        'mean_rgb_before':before.mean(axis=(0,1)).tolist(),'mean_rgb_after':after.mean(axis=(0,1)).tolist(),
        'before_sha256':digest(before_path),'after_sha256':digest(after_path)}
    save(state_path,state)
    print(json.dumps(state['acceptance'],ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
