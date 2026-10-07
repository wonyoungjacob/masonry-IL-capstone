"""Browse recorded dataset episodes and launch live MuJoCo policy rollouts."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import webbrowser

ROOT = Path(__file__).resolve().parent


def gallery():
    import pyarrow.parquet as pq

    datasets = []
    for root in sorted((ROOT / "data").iterdir()):
        if not (root / "meta/info.json").exists():
            continue
        info = json.loads((root / "meta/info.json").read_text())
        cameras = [k for k, v in info["features"].items() if v["dtype"] == "video"]
        rows = []
        for path in sorted((root / "meta/episodes").rglob("*.parquet")):
            rows.extend(pq.read_table(path).to_pylist())
        metrics_path = root / "episode_metrics.json"
        kept = [m for m in json.loads(metrics_path.read_text()) if m.get("kept")] if metrics_path.exists() else []
        episodes = []
        for row in sorted(rows, key=lambda r: r["episode_index"]):
            index = int(row["episode_index"])
            videos = []
            for cam in cameras:
                key = "videos/" + cam
                path = root / "videos" / cam / f"chunk-{int(row[key + '/chunk_index']):03d}" / f"file-{int(row[key + '/file_index']):03d}.mp4"
                videos.append(dict(camera=cam.split('.')[-1], url=path.as_uri(),
                                   start=row[key + '/from_timestamp'], end=row[key + '/to_timestamp']))
            metric = kept[index] if index < len(kept) else {}
            episodes.append(dict(index=index, videos=videos, seed=metric.get("episode_seed"),
                                 recovery=metric.get("recoveries"), success=metric.get("m1_all_success")))
        datasets.append(dict(name=root.name, episodes=episodes))
    html = '''<!doctype html><meta charset="utf-8"><title>조적 데이터셋 영상</title>
<style>body{background:#15202b;color:#eee;font:18px sans-serif;margin:32px}select,button{font-size:18px;padding:8px;margin:6px}#views{display:flex;gap:20px;flex-wrap:wrap}video{width:384px;max-width:90vw;background:#000}p{line-height:1.6}</style>
<h1>실제 수집 데이터셋</h1>
<p>저장된 카메라 영상입니다. 에피소드를 선택한 뒤 재생하세요. 원본 해상도는 128×128이며 화면에서 확대됩니다.<br>좌표 전용(state) 데이터셋에는 영상이 없습니다. MuJoCo 자유 시점은 터미널의 전문가·정책 실행 메뉴를 사용하세요.</p>
<select id="dataset"></select><select id="episode"></select><button id="play">함께 재생</button><button id="pause">일시정지</button><button id="restart">처음부터</button>
<p id="detail"></p><div id="views"></div>
<p>영상이 표시되지 않으면 AV1 재생을 지원하는 브라우저에서 이 파일을 여세요.</p>
<script>
const data=__DATA__;
const ds=document.querySelector('#dataset'), ep=document.querySelector('#episode'), views=document.querySelector('#views');
data.forEach((d,i)=>ds.add(new Option(d.name,i)));
let active=[];
function selectEpisode(){
 active.forEach(v=>v.pause()); active=[]; views.replaceChildren();
 const e=data[ds.value].episodes[ep.value]; if(!e)return;
 document.querySelector('#detail').textContent=`에피소드 ${e.index} · 수집 시드 ${e.seed ?? '미기록'} · 복구 ${e.recovery ?? '미기록'} · 세 벽돌 모두 성공: ${e.success ?? '미기록'}`;
 e.videos.forEach(item=>{
  const box=document.createElement('div'), label=document.createElement('p'), v=document.createElement('video');
  label.textContent=item.camera; v.controls=true; v.preload='metadata'; v.muted=true;
  v.src=item.url+'#t='+item.start+','+item.end;
  v.addEventListener('loadedmetadata',()=>{v.currentTime=item.start});
  v.addEventListener('timeupdate',()=>{if(v.currentTime>=item.end)v.pause()});
  v.dataset.start=item.start; v.dataset.end=item.end;
  box.append(label,v); views.append(box); active.push(v);
 });
 if(!e.videos.length)views.textContent='좌표 전용 데이터셋: 저장된 영상 없음';
}
function selectDataset(){ep.replaceChildren();data[ds.value].episodes.forEach((e,i)=>ep.add(new Option('에피소드 '+e.index,i)));selectEpisode()}
ds.onchange=selectDataset;ep.onchange=selectEpisode;
document.querySelector('#play').onclick=()=>active.forEach(v=>{if(v.currentTime>=Number(v.dataset.end)||v.currentTime<Number(v.dataset.start))v.currentTime=Number(v.dataset.start);v.play().catch(console.error)});
document.querySelector('#pause').onclick=()=>active.forEach(v=>v.pause());
document.querySelector('#restart').onclick=()=>active.forEach(v=>{v.pause();v.currentTime=Number(v.dataset.start)});
if(data.length)selectDataset();
</script>'''.replace('__DATA__', json.dumps(datasets, ensure_ascii=False).replace('<', '\\u003c'))
    path = ROOT / 'outputs/dataset_gallery.html'
    path.parent.mkdir(exist_ok=True)
    path.write_text(html, encoding='utf-8')
    print(f"데이터셋 {len(datasets)}종, 에피소드 {sum(len(d['episodes']) for d in datasets)}개: {path}")
    return path


def launch(checkpoint, args):
    cmd = [sys.executable, str(ROOT / 'view_demo.py'), '--task', '2p1', '--mortar', 'mortarB',
           '--size-rand', '0', '--pos-rand', '0.005', '--yaw-rand', '10',
           '--seed', str(args.seed), '--speed', str(args.speed)]
    if checkpoint:
        cmd += ['--ckpt', str(checkpoint), '--device', args.device, '--disturb', str(int(args.kick))]
        config = json.loads((checkpoint / 'train_config.json').read_text())
        if config.get('rename_map'):
            cmd += ['--rename-map', json.dumps(config['rename_map'])]
    print('MuJoCo 실행: 마우스로 회전·확대, Esc로 닫기. 완료 후 창은 유지됩니다.', flush=True)
    print('정책은 새로 실행됩니다. 과거 평가 영상의 재생이 아니므로 확률적 정책 결과는 달라질 수 있습니다.', flush=True)
    env = dict(os.environ, MUJOCO_GL='glfw')
    return subprocess.run(cmd, cwd=ROOT, env=env).returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--gallery', action='store_true', help='generate gallery without opening a browser')
    parser.add_argument('--seed', type=int, default=10000)
    parser.add_argument('--speed', type=float, default=1)
    parser.add_argument('--device', default='cuda')
    parser.add_argument('--kick', action='store_true', help='one disturbance during policy rollout')
    args = parser.parse_args()
    models = sorted(p for p in (ROOT / 'outputs').glob('*/checkpoints/last/pretrained_model')
                    if (p / 'train_config.json').exists())
    if args.gallery:
        gallery()
        return
    while True:
        print('\nD: 데이터셋 저장 영상 전체 / E: IK 전문가 MuJoCo / Q: 종료')
        for i, path in enumerate(models, 1):
            print(f'{i:2}: {path.parents[2].name}')
        print(f'시드 {args.seed} · 정책 교란 {args.kick} · 장면 mortarB')
        if args.list:
            return
        value = input('선택: ').strip().lower()
        if value == 'q':
            return
        if value == 'd':
            webbrowser.open(gallery().as_uri())
        elif value == 'e':
            launch(None, args)
        elif value.isdigit() and 1 <= int(value) <= len(models):
            launch(models[int(value) - 1], args)


if __name__ == '__main__':
    main()
