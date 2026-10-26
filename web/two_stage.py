"""Local proposal prototype: YOLO regions followed by frozen MobileNetV3 heads."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'proposal-pipeline'))
MAPPING = {'cap_absent':'head_covering','mask_uncovered':'mask_coverage',
 'uniform_absent':'workwear','table_uncleared':'table_clearance',
 'bread_shelf_underfilled':'bread_display_gaps','cashier_vacancy':'cashier_occupancy'}
_runtime = None

def ready():
    import importlib.util
    ok = all(importlib.util.find_spec(x) for x in ('torch','torchvision','ultralytics'))
    configured = (ROOT/'proposal-pipeline/models/registry.json').is_file()
    return dict(available=bool(ok and configured),configured=configured,assets_ready=configured)

class Runtime:
    def __init__(self):
        import torch
        from torchvision import transforms as T
        from ultralytics import YOLO
        from deviationlab_proposal_pipeline.local_models import TorchvisionMobileNetV3Classifier
        torch.set_num_threads(2)
        self.registry=json.loads((ROOT/'proposal-pipeline/models/registry.json').read_text())
        base=ROOT/'proposal-pipeline/models'
        self.locator_registry=json.loads((ROOT/'localizers/registry.json').read_text())
        self.detectors={}
        for name,spec in self.locator_registry.items():
            path=ROOT/'localizers'/spec['file']
            if hashlib.sha256(path.read_bytes()).hexdigest()!=spec['sha256']:
                raise ValueError('Localizer checksum mismatch')
            self.detectors[name]=YOLO(str(path))
        paths={}; labels={}; transforms={}; thresholds={}
        for target,spec in self.registry['targets'].items():
            paths[target]=base/spec['weights']
            if hashlib.sha256(paths[target].read_bytes()).hexdigest()!=spec['weights_sha256']:
                raise ValueError('Classifier checksum mismatch')
            p=spec['preprocessing']
            transforms[target]=T.Compose([T.Resize(p['resize'],interpolation=getattr(T.InterpolationMode,p.get('interpolation','bilinear').upper())),T.CenterCrop(p['crop']),T.ToTensor(),T.Normalize(p['mean'],p['std'])])
            labels[target]=spec['judgment_by_class_index']; thresholds[target]=spec['decision_threshold']
        self.classifier=TorchvisionMobileNetV3Classifier(paths,labels,transforms,thresholds)

    def analyze(self,path,scene,roi):
        from PIL import Image
        im=Image.open(path).convert('RGB'); w,h=im.size
        def detect(name,classes=None):
            result=self.detectors[name].predict(im,device='cpu',imgsz=960,conf=.25,classes=classes,verbose=False)[0]
            return [[max(0.,float(b[0])),max(0.,float(b[1])),min(w,float(b[2])),min(h,float(b[3]))] for b in result.boxes.xyxy.tolist()]
        if scene=='kitchen':
            heads=detect('head'); bodies=detect('general',[0])
            regions={'cap_absent':heads,'mask_uncovered':heads,'uniform_absent':[[a,b,c,b+.85*(d-b)] for a,b,c,d in bodies]}
        else:
            tables=detect('general',[60]); bread=detect('bread'); people=detect('general',[0])
            regions={'table_uncleared':tables,'bread_shelf_underfilled':bread,'cashier_vacancy':[[roi[0]*w,roi[1]*h,roi[2]*w,roi[3]*h]] if roi else []}
        rows=[]
        for key,boxes in regions.items():
            target=MAPPING[key]; observations=[]
            for box in boxes[:50]:
                if box[2]<=box[0] or box[3]<=box[1]: continue
                c=self.classifier.classify(im.crop(tuple(box)),target)
                observations.append({'box_xyxy':box,'judgment':c.judgment.value,'score':c.score,
                  'classifier_sha256':self.registry['targets'][target]['weights_sha256']})
            missing_roi=key=='cashier_vacancy' and not roi
            status='uncertain'; score=None
            if observations:
                selected=[o for o in observations if o['judgment']=='deviation'] or [o for o in observations if o['judgment']=='uncertain'] or observations
                judgment=selected[0]['judgment']; status={'deviation':'present','no_deviation':'absent','uncertain':'uncertain'}[judgment]
                score=max(o['score'] for o in selected) if status!='uncertain' else None
                evidence='MobileNetV3 classified the localized regions; review the region observations in the export.'
            else:
                selected=[]; evidence='Draw the cashier employee area to run this check.' if missing_roi else 'No relevant region was localized. Compliance cannot be determined.'
            normalized=[[round(o['box_xyxy'][0]/w*1000,3),round(o['box_xyxy'][1]/h*1000,3),round(o['box_xyxy'][2]/w*1000,3),round(o['box_xyxy'][3]/h*1000,3)] for o in selected]
            row={'type':key,'status':'not_applicable' if missing_roi else status,'execution_status':'configuration_required' if missing_roi else 'completed',
              'evidence':evidence,'score':score,'boxes_1000':normalized,'bbox_1000':normalized[0] if normalized else None,
              'decision_route':'yolo-roi-mobilenetv3-v2','region_observations':observations,
              'localizer_hashes':{n:s['sha256'] for n,s in self.locator_registry.items()}}
            if key=='cashier_vacancy':
                row['localization_method']='user-defined employee area; YOLO person boxes retained as supporting evidence'
                row['person_boxes_xyxy']=people
            rows.append(row)
        return {'assessments':rows,'provider_model':'mobilenetv3-roi-v2','protocol':'proposal-two-stage-001'}

def analyze(path,scene,roi):
    global _runtime
    if _runtime is None: _runtime=Runtime()
    return _runtime.analyze(path,scene,roi)
