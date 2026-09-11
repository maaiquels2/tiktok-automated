import { useEffect } from 'react';
import { ReactFlow, Background, Controls, Handle, Position, useNodesState, useReactFlow, ReactFlowProvider } from '@xyflow/react';
import { UserRound, Shirt, Image, Check, Clapperboard, Type, Upload, RotateCcw, LockKeyhole, LineChart } from 'lucide-react';
import { nextStage, stageInfo } from './api';
const icons={user:UserRound,shirt:Shirt,image:Image,check:Check,video:Clapperboard,text:Type,upload:Upload,chart:LineChart};
const defaultPositions=Object.fromEntries(stageInfo.map((s,i)=>[s.id,{x:(i%4)*255,y:Math.floor(i/4)*225}]));
function StageNode({data,selected}) {
  const Icon=icons[data.icon];
  return <div className={`stage-node ${data.state} ${selected?'selected':''}`}>
    <Handle type="target" position={Position.Left}/>
    <div className="node-top"><span className="node-number">{String(data.index+1).padStart(2,'0')}</span><span className="node-status">{data.state==='done'?<><Check size={12}/>Concluído</>:data.state==='current'?'Em foco':'A seguir'}</span></div>
    <div className="node-icon"><Icon size={23}/></div><h3>{data.title}</h3><p>{data.subtitle}</p>
    <div className="node-footer">{data.footer}{data.id.includes('approval')&&<LockKeyhole size={13}/>}</div>
    <Handle type="source" position={Position.Right}/>
  </div>;
}
const nodeTypes={stage:StageNode};
function FlowCanvas({campaign,selected,onSelect,onLayout,busy}) {
  const [nodes,setNodes,onNodesChange]=useNodesState([]);
  const flow=useReactFlow();
  const current=stageInfo.findIndex(s=>s.id===nextStage(campaign));
  useEffect(()=>{
    setNodes(stageInfo.map((s,i)=>({id:s.id,type:'stage',selected:selected===s.id,position:campaign.layout[s.id]||defaultPositions[s.id],
      data:{...s,index:i,state:campaign.status==='published'||i<current?'done':i===current?'current':'waiting',
      footer:s.id==='image'||s.id==='video'?`${campaign.generator==='flow'?'FLOW · 1080p':'GROK · 720p'}`:s.id.includes('approval')?'REVISÃO HUMANA':s.id==='studio'?'MICAELA · TIKTOK':'SALVO LOCALMENTE'}})));
  },[campaign,selected,current,setNodes]);
  const edges=stageInfo.slice(1).map((s,i)=>({id:'e'+i,source:stageInfo[i].id,target:s.id,type:'smoothstep',
    style:{stroke:i<current?'#9579e9':'#ccc5dc',strokeWidth:1.7},animated:false}));
  const positions=list=>Object.fromEntries(list.map(n=>[n.id,n.position]));
  return <div className="canvas"><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange}
    onNodeClick={(_,node)=>onSelect(node.id)} onNodeDragStop={(_,node)=>onLayout(positions(nodes.map(n=>n.id===node.id?node:n)))}
    nodesDraggable={!busy} nodesConnectable={false} edgesReconnectable={false} deleteKeyCode={null} fitView fitViewOptions={{padding:.16,maxZoom:.9}}
    minZoom={.25} maxZoom={1.5} proOptions={{hideAttribution:false}}><Background color="#d7d2e2" gap={22}/><Controls showInteractive={false}/>
    <div className="canvas-tools"><button onClick={()=>{onLayout({});setNodes(ns=>ns.map(n=>({...n,position:defaultPositions[n.id]})));requestAnimationFrame(()=>flow.fitView({padding:.16,maxZoom:.9}));}} disabled={busy}><RotateCcw size={14}/> Organizar</button></div>
  </ReactFlow><div className="canvas-legend"><span><i className="legend-dot done"/>Concluído</span><span><i className="legend-dot current"/>Etapa atual</span><span><i className="legend-dot"/>A seguir</span></div></div>;
}
export default function Canvas(props){return <ReactFlowProvider><FlowCanvas {...props}/></ReactFlowProvider>}
