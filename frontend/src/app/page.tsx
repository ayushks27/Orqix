'use client'

import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { 
  Layers, 
  LineChart as ChartIcon, 
  Monitor, 
  GitBranch, 
  Cpu, 
  Share2, 
  Package, 
  Sparkles, 
  User, 
  Plus, 
  Play, 
  Check, 
  RefreshCw, 
  AlertCircle,
  Database,
  Terminal,
  Activity,
  History,
  Info,
  TrendingUp,
  Server,
  ChevronRight,
  ExternalLink,
  Sliders,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  X
} from 'lucide-react'
import { ReactFlow, Background, Controls } from '@xyflow/react'
import '@xyflow/react/dist/style.css'

import { Line, Bar, Doughnut } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

interface Run {
  id: string
  parent_run_id?: string
  status: 'COMPLETED' | 'FAILED' | 'RUNNING'
  git_commit: string
  dataset_version: string
  parameters: string
  metrics: string
  created_at?: string
  completed_at?: string
}

interface Experiment {
  id: string
  name: string
  created_at: string
}

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<'experiments' | 'runs' | 'workflows' | 'scheduler' | 'lineage' | 'registry' | 'agent'>('experiments')
  
  // E2E Backend States
  const [token, setToken] = useState<string>('')
  const [backendStatus, setBackendStatus] = useState<'connected' | 'simulated'>('simulated')
  const [experiments, setExperiments] = useState<Experiment[]>([])
  const [selectedExp, setSelectedExp] = useState<string>('')
  const [runs, setRuns] = useState<Run[]>([])
  
  // Selected items for drawers/detail views
  const [selectedRun, setSelectedRun] = useState<Run | null>(null)
  
  // Agent States
  const [agentRun, setAgentRun] = useState('')
  const [agentResult, setAgentResult] = useState<any>(null)
  const [agentLoading, setAgentLoading] = useState(false)
  
  // Registry States
  const [models, setModels] = useState<any[]>([])
  const [selectedModel, setSelectedModel] = useState<any>(null)
  const [versions, setVersions] = useState<any[]>([])
  const [isPromoting, setIsPromoting] = useState<string | null>(null)
  const [promotionStage, setPromotionStage] = useState<'STAGING' | 'PRODUCTION' | 'ARCHIVED'>('STAGING')
  const [promotionNotes, setPromotionNotes] = useState('')

  // Health States
  const [dbHealth, setDbHealth] = useState<'online' | 'offline'>('online')
  const [redisHealth, setRedisHealth] = useState<'online' | 'offline'>('online')
  const [kafkaHealth, setKafkaHealth] = useState<'online' | 'offline'>('offline')

  useEffect(() => {
    async function checkHealth() {
      try {
        const res = await fetch('http://localhost:8000/health')
        if (res.ok) {
          const data = await res.json()
          setDbHealth(data.postgres)
          setRedisHealth(data.redis)
          setKafkaHealth(data.kafka)
        } else {
          setDbHealth('online')
          setRedisHealth('online')
          setKafkaHealth('offline')
        }
      } catch (err) {
        setDbHealth('online')
        setRedisHealth('online')
        setKafkaHealth('offline')
      }
    }
    checkHealth()
    const interval = setInterval(checkHealth, 5000)
    return () => clearInterval(interval)
  }, [])

  // Simulation states
  const [simModel, setSimModel] = useState('Transformer')
  const [simBatch, setSimBatch] = useState(128)
  const [simFail, setSimFail] = useState(false)
  const [consoleOutput, setConsoleOutput] = useState('[SYSTEM] Telemetry channel opened.\n[SYSTEM] Ready for telemetry...')
  const [isSimulating, setIsSimulating] = useState(false)

  // Seed mock data
  const mockExperiments = useMemo(() => [
    { id: 'exp_001', name: 'MNIST_Digit_CNN_Classifier', created_at: '2026-06-16T13:50:00Z' },
    { id: 'exp_002', name: 'LLM_FineTuning_LoRA', created_at: '2026-06-16T13:51:00Z' }
  ], [])

  const mockRuns = useMemo(() => [
    { id: 'run_f72b9a81', status: 'COMPLETED', git_commit: 'e82b7a', dataset_version: 'mnist_v2', parameters: 'batch_size:64, lr:0.01', metrics: 'loss:0.045, acc:0.985', created_at: '2026-06-16T13:52:00Z', completed_at: '2026-06-16T13:58:30Z' },
    { id: 'run_e09a1c1d', status: 'FAILED', git_commit: 'd8e412', dataset_version: 'mnist_v3', parameters: 'batch_size:256, lr:0.01', metrics: 'loss:1.340, acc:0.420', created_at: '2026-06-16T13:53:00Z', completed_at: '2026-06-16T13:55:12Z' }
  ] as Run[], [])

  const mockModels = useMemo(() => [
    { id: 'mod_1', name: 'resnet50-mnist-classifier', description: 'Production ResNet classifier for digit logs.', version_count: 2, production_version: 'v1.0.0', created_at: '2026-06-16T13:50:00Z' },
    { id: 'mod_2', name: 'transformer-text-gen', description: 'Transformer sequence model for text auto-completion.', version_count: 1, production_version: null, created_at: '2026-06-16T13:52:00Z' }
  ], [])

  const mockVersions = useMemo(() => [
    { id: 'mv_903d12', version: 'v1.0.0', run_id: 'run_f72b9a81', artifact_uri: 's3://orqix-artifacts/resnet_model.pt', stage: 'PRODUCTION', created_at: '2026-06-16T13:58:00Z', history: [
      { approver: 'usr_admin', from_stage: 'DEVELOPMENT', to_stage: 'STAGING', approved_at: '2026-06-16T13:59:00Z', notes: 'Verified validation accuracy' },
      { approver: 'usr_admin', from_stage: 'STAGING', to_stage: 'PRODUCTION', approved_at: '2026-06-16T14:02:00Z', notes: 'Passed deployment checks' }
    ]},
    { id: 'mv_903d13', version: 'v1.1.0-rc1', run_id: 'run_e09a1c1d', artifact_uri: 's3://orqix-artifacts/resnet_model_new.pt', stage: 'DEVELOPMENT', created_at: '2026-06-16T14:05:00Z', history: [] }
  ], [])

  // Auto Login and Fetch Backend status
  useEffect(() => {
    async function initAuth() {
      try {
        const res = await fetch('http://localhost:8000/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            email: 'researcher@orqix.ai',
            password: 'researcher_pass'
          })
        })
        if (res.ok) {
          const data = await res.json()
          setToken(data.access_token)
          setBackendStatus('connected')
        } else {
          setBackendStatus('simulated')
          setExperiments(mockExperiments)
          setSelectedExp('exp_001')
          setRuns(mockRuns)
          setModels(mockModels)
        }
      } catch (err) {
        setBackendStatus('simulated')
        setExperiments(mockExperiments)
        setSelectedExp('exp_001')
        setRuns(mockRuns)
        setModels(mockModels)
      }
    }
    initAuth()
  }, [mockExperiments, mockRuns, mockModels])

  // Sync / Load data
  const handleSync = useCallback(async () => {
    if (backendStatus === 'simulated') {
      setExperiments(mockExperiments)
      setRuns(mockRuns)
      setModels(mockModels)
      return
    }

    try {
      // Fetch Experiments
      const expRes = await fetch('http://localhost:8001/experiments', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (expRes.ok) {
        const expData = await expRes.ok ? await expRes.json() : []
        setExperiments(expData)
        if (expData.length > 0 && !selectedExp) {
          setSelectedExp(expData[0].id)
        }
      }

      // Fetch Models
      const modelRes = await fetch('http://localhost:8005/registry/models', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
      if (modelRes.ok) {
        const modelData = await modelRes.json()
        setModels(modelData)
      }
    } catch (err) {
      console.error("E2E Sync failed, using mock fallbacks:", err)
    }
  }, [backendStatus, token, mockExperiments, mockRuns, mockModels, selectedExp])

  // Fetch runs when selected experiment changes
  useEffect(() => {
    if (!selectedExp) return
    if (backendStatus === 'simulated') {
      setRuns(mockRuns)
      return
    }

    async function getRuns() {
      try {
        const res = await fetch(`http://localhost:8001/experiments/${selectedExp}/runs`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
        if (res.ok) {
          const data = await res.json()
          const formatted = data.map((r: any) => ({
            id: r.id,
            status: r.status,
            git_commit: r.git_commit || 'N/A',
            dataset_version: r.dataset_version || 'N/A',
            parameters: Object.entries(r.parameters || {}).map(([k,v]) => `${k}:${v}`).join(', ') || 'N/A',
            metrics: Object.entries(r.metrics || {}).map(([k,v]) => `${k}:${v}`).join(', ') || 'N/A',
            created_at: r.created_at,
            completed_at: r.completed_at
          }))
          setRuns(formatted)
        }
      } catch (err) {
        setRuns(mockRuns)
      }
    }
    getRuns()
  }, [selectedExp, backendStatus, token, mockRuns])

  // Fetch versions when selected model changes
  useEffect(() => {
    if (!selectedModel) return
    if (backendStatus === 'simulated') {
      setVersions(mockVersions)
      return
    }

    async function getVersions() {
      try {
        const res = await fetch(`http://localhost:8005/registry/models/${selectedModel.id}/versions`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
        if (res.ok) {
          const data = await res.json()
          setVersions(data)
        }
      } catch (err) {
        setVersions(mockVersions)
      }
    }
    getVersions()
  }, [selectedModel, backendStatus, token, mockVersions])

  // Execute Simulation
  const handleSimulateRun = () => {
    if (isSimulating) return
    setIsSimulating(true)
    setActiveTab('runs')
    setConsoleOutput((prev: string) => prev + `\n[RUNNER] Launching worker container on Kubernetes node...\n[RUNNER] Allocating resources: GPU=1, CPU=4, MEM=16GB\n[RUNNER] Running command: train.py --model=${simModel} --batch_size=${simBatch}\n`)
    
    // Simulate steps
    setTimeout(() => {
      setConsoleOutput((prev: string) => prev + `[EPOCH 1/10] Loss: 2.15 - Acc: 0.22 | Mem: 4.8 GB/16 GB\n`)
    }, 1000)
    setTimeout(() => {
      setConsoleOutput((prev: string) => prev + `[EPOCH 2/10] Loss: 1.62 - Acc: 0.45 | Mem: 8.2 GB/16 GB\n`)
    }, 2000)
    
    if (simFail) {
      setTimeout(() => {
        setConsoleOutput((prev: string) => prev + `[EPOCH 3/10] Loss: NaN - Acc: 0.18\n[FATAL] CUDA Out of Memory (OOM). Tried to allocate 4.20 GiB. GPU 0 has 11.20 GiB total capacity.\n[SYSTEM] Run status set to FAILED.\n`)
        setIsSimulating(false)
        const newRun: Run = {
          id: `run_${Math.random().toString(36).substr(2, 8)}`,
          status: 'FAILED',
          git_commit: '8bf97e',
          dataset_version: 'mnist_v3',
          parameters: `batch_size:${simBatch}, model:${simModel}`,
          metrics: 'loss:NaN, acc:0.18',
          created_at: new Date().toISOString()
        }
        setRuns(prev => [newRun, ...prev])
      }, 3000)
    } else {
      setTimeout(() => {
        setConsoleOutput((prev: string) => prev + `[EPOCH 10/10] Loss: 0.08 - Acc: 0.97 | Mem: 12.1 GB/16 GB\n[RUNNER] Uploading checkpoints to MinIO S3 bucket: 'orqix-artifacts'\n[SYSTEM] Run completed successfully.\n`)
        setIsSimulating(false)
        const newRun: Run = {
          id: `run_${Math.random().toString(36).substr(2, 8)}`,
          status: 'COMPLETED',
          git_commit: '8bf97e',
          dataset_version: 'mnist_v3',
          parameters: `batch_size:${simBatch}, model:${simModel}`,
          metrics: 'loss:0.080, acc:0.970',
          created_at: new Date().toISOString()
        }
        setRuns(prev => [newRun, ...prev])
      }, 3500)
    }
  }

  // AI Failure Diagnosis
  const handleDiagnose = async () => {
    if (!agentRun) return
    setAgentLoading(true)
    setAgentResult(null)
    
    if (backendStatus === 'simulated') {
      setTimeout(() => {
        setAgentLoading(false)
        setAgentResult({
          failure_category: 'GPU Out of Memory (OOM)',
          root_cause: 'CUDA allocations exceeded GPU memory constraints on the cluster node.',
          explanation: `The run failed because batch size ${simBatch} requires more tensor buffers than the V100 GPU pod capacity of 16GB.`,
          recommendations: [
            `Reduce batch size from ${simBatch} to ${simBatch / 2}.`,
            'Enable gradient accumulation steps in the training script.',
            'Request a nodeset with high-memory GPUs (e.g. A100).'
          ]
        })
      }, 1500)
      return
    }

    try {
      const res = await fetch('http://localhost:8006/agent/diagnose', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ run_id: agentRun })
      })
      if (res.ok) {
        const data = await res.json()
        setAgentResult(data)
      } else {
        throw new Error("Diagnosis service failed")
      }
    } catch (err) {
      setAgentResult({
        failure_category: 'GPU Out of Memory (OOM)',
        root_cause: 'CUDA allocations exceeded GPU memory constraints.',
        explanation: 'The system failed because the batch size exceeded memory bounds.',
        recommendations: ['Reduce batch size by 50%.', 'Enable mixed precision (FP16) training.']
      })
    } finally {
      setAgentLoading(false)
    }
  }

  // Model Promotion
  const handlePromote = async () => {
    if (!isPromoting) return
    
    if (backendStatus === 'simulated') {
      setVersions(prev => prev.map(v => v.id === isPromoting ? {
        ...v,
        stage: promotionStage,
        history: [{
          approver: 'researcher@orqix.ai',
          from_stage: v.stage,
          to_stage: promotionStage,
          approved_at: new Date().toISOString(),
          notes: promotionNotes
        }, ...v.history]
      } : v))
      setIsPromoting(null)
      setPromotionNotes('')
      return
    }

    try {
      const res = await fetch(`http://localhost:8005/registry/versions/${isPromoting}/promote`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          to_stage: promotionStage,
          notes: promotionNotes
        })
      })
      if (res.ok) {
        const listRes = await fetch(`http://localhost:8005/registry/models/${selectedModel.id}/versions`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
        if (listRes.ok) {
          const listData = await listRes.json()
          setVersions(listData)
        }
      }
    } catch (err) {
      console.error("Failed model promotion E2E:", err)
    } finally {
      setIsPromoting(null)
      setPromotionNotes('')
    }
  }

  useEffect(() => {
    handleSync()
  }, [activeTab, handleSync])

  // Custom visual components data (Monochrome Styled)
  const chartsData = useMemo(() => {
    return {
      lossAcc: {
        labels: ['Epoch 1', 'Epoch 2', 'Epoch 3', 'Epoch 4', 'Epoch 5', 'Epoch 6', 'Epoch 7', 'Epoch 8', 'Epoch 9', 'Epoch 10'],
        datasets: [
          {
            label: 'Loss',
            data: [0.95, 0.72, 0.48, 0.35, 0.22, 0.17, 0.12, 0.09, 0.07, 0.045],
            borderColor: '#a3a3a3', // neutral-400
            backgroundColor: 'rgba(255, 255, 255, 0.02)',
            tension: 0.4,
            fill: true,
            yAxisID: 'y'
          },
          {
            label: 'Accuracy',
            data: [0.65, 0.78, 0.84, 0.89, 0.92, 0.94, 0.96, 0.97, 0.98, 0.985],
            borderColor: '#ffffff', // pure white
            borderDash: [5, 5],
            backgroundColor: 'transparent',
            tension: 0.4,
            fill: false,
            yAxisID: 'y1'
          }
        ]
      },
      gpuAllocation: {
        labels: ['Allocated Memory', 'Idle Memory'],
        datasets: [{
          data: [82, 18],
          backgroundColor: ['#ffffff', 'rgba(255, 255, 255, 0.06)'],
          borderWidth: 0
        }]
      },
      gpuNodeMemory: {
        labels: ['node-v100-0', 'node-v100-1', 'node-a100-0', 'node-a100-1'],
        datasets: [{
          label: 'Used GPU Memory (GB)',
          data: [14.2, 6.4, 38.0, 0.0],
          backgroundColor: '#52525b', // neutral-600
          hoverBackgroundColor: '#ffffff', // white highlight
          borderRadius: 8
        }]
      }
    }
  }, [])

  // Workflow DAG React Flow nodes/edges (Monochrome Styled)
  const { dagNodes, dagEdges } = useMemo(() => {
    const nodes = [
      {
        id: '1',
        type: 'default',
        position: { x: 50, y: 150 },
        data: {
          label: (
            <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-xl flex items-center gap-2.5 shadow-md">
              <Database className="w-4 h-4 text-zinc-300" />
              <div className="text-left">
                <p className="text-xs font-semibold text-white">dataset_ingestion</p>
                <p className="text-[10px] text-zinc-500 font-mono">mnist_v3 (MinIO)</p>
              </div>
            </div>
          )
        },
        style: { width: 180, border: 'none', background: 'transparent', padding: 0 }
      },
      {
        id: '2',
        type: 'default',
        position: { x: 280, y: 150 },
        data: {
          label: (
            <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-xl flex items-center gap-2.5 shadow-md">
              <Sliders className="w-4 h-4 text-zinc-300" />
              <div className="text-left">
                <p className="text-xs font-semibold text-white">preprocessing</p>
                <p className="text-[10px] text-zinc-500 font-mono font-semibold">scaling & normalization</p>
              </div>
            </div>
          )
        },
        style: { width: 180, border: 'none', background: 'transparent', padding: 0 }
      },
      {
        id: '3',
        type: 'default',
        position: { x: 510, y: 50 },
        data: {
          label: (
            <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-xl flex items-center gap-2.5 shadow-md">
              <Cpu className="w-4 h-4 text-zinc-300" />
              <div className="text-left">
                <p className="text-xs font-semibold text-white">training_cnn</p>
                <p className="text-[10px] text-zinc-500 font-mono">resnet50 classifier</p>
              </div>
            </div>
          )
        },
        style: { width: 180, border: 'none', background: 'transparent', padding: 0 }
      },
      {
        id: '4',
        type: 'default',
        position: { x: 510, y: 250 },
        data: {
          label: (
            <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-xl flex items-center gap-2.5 shadow-md">
              <Cpu className="w-4 h-4 text-zinc-300" />
              <div className="text-left">
                <p className="text-xs font-semibold text-white">training_transformer</p>
                <p className="text-[10px] text-zinc-500 font-mono">12-layer attention</p>
              </div>
            </div>
          )
        },
        style: { width: 180, border: 'none', background: 'transparent', padding: 0 }
      },
      {
        id: '5',
        type: 'default',
        position: { x: 740, y: 150 },
        data: {
          label: (
            <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-xl flex items-center gap-2.5 shadow-md">
              <Activity className="w-4 h-4 text-zinc-300" />
              <div className="text-left">
                <p className="text-xs font-semibold text-white">evaluation</p>
                <p className="text-[10px] text-zinc-500 font-mono">metrics validation</p>
              </div>
            </div>
          )
        },
        style: { width: 180, border: 'none', background: 'transparent', padding: 0 }
      },
      {
        id: '6',
        type: 'default',
        position: { x: 970, y: 150 },
        data: {
          label: (
            <div className="p-3 bg-zinc-900 border border-zinc-700 rounded-xl flex items-center gap-2.5 shadow-md">
              <CheckCircle2 className="w-4 h-4 text-white" />
              <div className="text-left">
                <p className="text-xs font-semibold text-white">registry_promote</p>
                <p className="text-[10px] text-zinc-400 font-mono">push production version</p>
              </div>
            </div>
          )
        },
        style: { width: 180, border: 'none', background: 'transparent', padding: 0 }
      }
    ]

    const edges = [
      { id: 'e1-2', source: '1', target: '2', animated: true, style: { stroke: '#a3a3a3' } },
      { id: 'e2-3', source: '2', target: '3', animated: true, style: { stroke: '#737373' } },
      { id: 'e2-4', source: '2', target: '4', animated: true, style: { stroke: '#737373' } },
      { id: 'e3-5', source: '3', target: '5', animated: true, style: { stroke: '#525252' } },
      { id: 'e4-5', source: '4', target: '5', animated: true, style: { stroke: '#525252' } },
      { id: 'e5-6', source: '5', target: '6', animated: true, style: { stroke: '#d4d4d8' } }
    ]

    return { dagNodes: nodes, dagEdges: edges }
  }, [])

  // Lineage React Flow nodes/edges (Monochrome Styled)
  const { lineageNodes, lineageEdges } = useMemo(() => {
    const nodes = [
      {
        id: 'l1',
        type: 'default',
        position: { x: 50, y: 150 },
        data: {
          label: (
            <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-xl flex flex-col shadow-md">
              <span className="text-[10px] text-zinc-400 uppercase font-bold tracking-wider mb-1">Dataset S3</span>
              <p className="text-xs font-bold text-white">mnist_v3.tar.gz</p>
              <p className="text-[10px] text-zinc-500 font-mono mt-0.5">10.2 GB | sha:9a8d1b</p>
            </div>
          )
        },
        style: { width: 180, border: 'none', background: 'transparent', padding: 0 }
      },
      {
        id: 'l2',
        type: 'default',
        position: { x: 290, y: 50 },
        data: {
          label: (
            <div className="p-3 bg-zinc-900 border border-zinc-800 rounded-xl flex flex-col shadow-md">
              <span className="text-[10px] text-zinc-400 uppercase font-bold tracking-wider mb-1">Training Run</span>
              <p className="text-xs font-bold text-white">run_f72b9a81</p>
              <p className="text-[10px] text-white font-mono mt-0.5">COMPLETED (Acc: 0.985)</p>
            </div>
          )
        },
        style: { width: 180, border: 'none', background: 'transparent', padding: 0 }
      },
      {
        id: 'l3',
        type: 'default',
        position: { x: 290, y: 250 },
        data: {
          label: (
            <div className="p-3 bg-zinc-900 border border-zinc-850 rounded-xl flex flex-col shadow-md">
              <span className="text-[10px] text-zinc-400 uppercase font-bold tracking-wider mb-1">Training Run</span>
              <p className="text-xs font-bold text-white">run_e09a1c1d</p>
              <p className="text-[10px] text-zinc-500 font-mono mt-0.5">FAILED (OOM)</p>
            </div>
          )
        },
        style: { width: 180, border: 'none', background: 'transparent', padding: 0 }
      },
      {
        id: 'l4',
        type: 'default',
        position: { x: 530, y: 150 },
        data: {
          label: (
            <div className="p-3 bg-zinc-900 border border-zinc-700 rounded-xl flex flex-col shadow-md">
              <span className="text-[10px] text-white uppercase font-bold tracking-wider mb-1">Model Version</span>
              <p className="text-xs font-bold text-white">digits-cnn v1.0.0</p>
              <p className="text-[10px] text-zinc-400 font-mono mt-0.5">Stage: PRODUCTION</p>
            </div>
          )
        },
        style: { width: 180, border: 'none', background: 'transparent', padding: 0 }
      }
    ]

    const edges = [
      { id: 'el1-2', source: 'l1', target: 'l2', animated: true, style: { stroke: '#a3a3a3' } },
      { id: 'el1-3', source: 'l1', target: 'l3', animated: true, style: { stroke: '#525252' } },
      { id: 'el2-4', source: 'l2', target: 'l4', animated: true, style: { stroke: '#ffffff' } }
    ]

    return { lineageNodes: nodes, lineageEdges: edges }
  }, [])

  return (
    <div className="min-h-screen flex flex-col font-sans text-zinc-100 bg-black pb-8">
      {/* Top Navbar */}
      <header className="glass sticky top-0 z-50 px-6 py-4 flex items-center justify-between border-b border-zinc-900">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-white via-zinc-400 to-zinc-800 flex items-center justify-center shadow-lg shadow-white/5">
            <Layers className="w-5 h-5 text-black" />
          </div>
          <div>
            <span className="text-xl font-bold tracking-tight text-white flex items-center gap-2">
              ORQIX <span className="text-xs bg-zinc-900 border border-zinc-800 text-white px-2 py-0.5 rounded-full font-mono font-semibold">DISTRIBUTED</span>
            </span>
            <p className="text-[10px] text-zinc-500 tracking-wide uppercase">AI-Native ML Experiment & Control Plane</p>
          </div>
        </div>

        <div className="flex items-center gap-5">
          {/* E2E Backend Live Badge */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-zinc-900 border border-zinc-800 text-xs">
            <span className={`w-2 h-2 rounded-full ${backendStatus === 'connected' ? 'bg-white pulse-white' : 'bg-zinc-600'}`}></span>
            <span className="text-[11px] font-medium text-zinc-300">
              {backendStatus === 'connected' ? 'E2E Backend Connected' : 'Simulated Sandbox Mode'}
            </span>
          </div>

          <div className="flex items-center gap-3 border-l border-zinc-900 pl-5">
            <div className="text-right">
              <p className="text-xs font-semibold text-white font-mono">researcher@orqix.ai</p>
              <span className="text-[9px] bg-zinc-900 text-zinc-300 border border-zinc-800 px-2 py-0.5 rounded-full font-mono font-bold tracking-wider">RESEARCHER</span>
            </div>
            <div className="w-9 h-9 rounded-xl bg-zinc-900 flex items-center justify-center border border-zinc-800">
              <User className="w-4 h-4 text-zinc-400" />
            </div>
          </div>
        </div>
      </header>

      {/* Main Workspace Layout */}
      <div className="flex-1 flex flex-col lg:flex-row w-full px-4 lg:px-6 mt-6 gap-6">
        
        {/* Sidebar Dock Navigation */}
        <aside className="w-full lg:w-60 flex flex-col gap-2">
          <div className="glass-premium p-3 rounded-2xl flex flex-row lg:flex-col gap-1 w-full overflow-x-auto lg:overflow-x-visible pb-2 lg:pb-3">
            {[
              { id: 'experiments', label: 'Experiment Runs', icon: ChartIcon },
              { id: 'runs', label: 'Telemetry Console', icon: Terminal },
              { id: 'workflows', label: 'DAG Pipelines', icon: GitBranch },
              { id: 'scheduler', label: 'Compute Scheduler', icon: Cpu },
              { id: 'lineage', label: 'Data Lineage', icon: Share2 },
              { id: 'registry', label: 'Model Registry', icon: Package },
              { id: 'agent', label: 'AI Failure Agent', icon: Sparkles, color: 'text-white' }
            ].map(tab => {
              const Icon = tab.icon
              const isActive = activeTab === tab.id
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id as any)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl text-xs font-semibold tracking-wide transition-all ${
                    isActive 
                      ? 'text-white bg-zinc-900 border border-zinc-800 shadow-md font-bold' 
                      : 'text-zinc-400 hover:text-white hover:bg-zinc-900/30'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${tab.color || 'text-zinc-300'} ${isActive && tab.id === 'agent' ? 'pulse-white' : ''}`} />
                  {tab.label}
                </button>
              )
            })}
          </div>

          {/* Infrastructure Health Status */}
          <div className="hidden lg:flex glass p-4 rounded-2xl flex-col gap-2.5 mt-2">
            <span className="text-[10px] font-bold text-zinc-500 tracking-wider uppercase">Cluster Status</span>
            <div className="flex flex-col gap-2 text-xs">
              <div className="flex justify-between items-center">
                <span className="text-zinc-400 font-medium">PostgreSQL</span>
                <span className="text-white font-mono flex items-center gap-1">
                  <span className={`w-1.5 h-1.5 rounded-full ${dbHealth === 'online' ? 'bg-white pulse-white' : 'bg-zinc-700'}`}></span>
                  {dbHealth === 'online' ? 'Online' : 'Offline'}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-zinc-400 font-medium">Redis Cache</span>
                <span className="text-white font-mono flex items-center gap-1">
                  <span className={`w-1.5 h-1.5 rounded-full ${redisHealth === 'online' ? 'bg-white pulse-white' : 'bg-zinc-700'}`}></span>
                  {redisHealth === 'online' ? 'Online' : 'Offline'}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-zinc-400 font-medium">Redpanda Kafka</span>
                <span className="text-white font-mono flex items-center gap-1">
                  <span className={`w-1.5 h-1.5 rounded-full ${kafkaHealth === 'online' ? 'bg-white pulse-white' : 'bg-zinc-700'}`}></span>
                  {kafkaHealth === 'online' ? 'Online' : 'Offline'}
                </span>
              </div>
            </div>
          </div>
        </aside>

        {/* Dashboard Main Content Window */}
        <main className="flex-1 min-w-0">
          
          {/* Tab: Experiments */}
          {activeTab === 'experiments' && (
            <div className="flex flex-col gap-6">
              
              {/* Header Details */}
              <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
                <div>
                  <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                    <ChartIcon className="w-5 h-5 text-white" />
                    Experiment Tracking
                  </h2>
                  <p className="text-xs text-zinc-500 font-medium">Track and compare nested metrics, parameters, and metadata configurations.</p>
                </div>
                
                <div className="flex items-center gap-3 w-full md:w-auto">
                  <div className="flex-1 md:flex-initial min-w-[220px]">
                    <select 
                      value={selectedExp} 
                      onChange={e => setSelectedExp(e.target.value)}
                      className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-zinc-700 font-semibold font-mono"
                    >
                      {experiments.map(exp => (
                        <option key={exp.id} value={exp.id}>{exp.name}</option>
                      ))}
                    </select>
                  </div>
                  <button 
                    onClick={handleSync}
                    className="px-4 py-2 bg-zinc-900 border border-zinc-800 hover:bg-zinc-800 hover:border-zinc-700 text-white rounded-xl text-xs font-semibold flex items-center gap-2 transition"
                  >
                    <RefreshCw className="w-3.5 h-3.5" /> Sync Data
                  </button>
                </div>
              </div>

              {/* Experiments Quick Stats */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="glass p-4 rounded-2xl flex items-center gap-3">
                  <div className="w-10 h-10 bg-zinc-900 border border-zinc-800 text-white rounded-xl flex items-center justify-center">
                    <TrendingUp className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="text-[10px] text-zinc-500 tracking-wider uppercase font-bold">Total Runs logged</span>
                    <p className="text-lg font-bold text-white font-mono">{runs.length}</p>
                  </div>
                </div>
                <div className="glass p-4 rounded-2xl flex items-center gap-3">
                  <div className="w-10 h-10 bg-zinc-900 border border-zinc-800 text-white rounded-xl flex items-center justify-center">
                    <CheckCircle2 className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="text-[10px] text-zinc-500 tracking-wider uppercase font-bold">Completed Runs</span>
                    <p className="text-lg font-bold text-white font-mono">{runs.filter(r=>r.status==='COMPLETED').length}</p>
                  </div>
                </div>
                <div className="glass p-4 rounded-2xl flex items-center gap-3">
                  <div className="w-10 h-10 bg-zinc-900 border border-zinc-800 text-white rounded-xl flex items-center justify-center">
                    <Activity className="w-5 h-5" />
                  </div>
                  <div>
                    <span className="text-[10px] text-zinc-500 tracking-wider uppercase font-bold">Best Accuracy</span>
                    <p className="text-lg font-bold text-white font-mono">98.5%</p>
                  </div>
                </div>
              </div>

              {/* Runs Table */}
              <div className="glass rounded-2xl overflow-hidden border border-zinc-900">
                <div className="p-4 border-b border-zinc-900 bg-zinc-900/30 flex justify-between items-center">
                  <span className="text-xs font-bold text-white uppercase tracking-wider">Run History</span>
                  <span className="text-[10px] text-zinc-500 font-mono font-semibold">Click a row to open metrics inspector</span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-zinc-300">
                    <thead className="bg-zinc-900/60 text-zinc-500 uppercase text-[10px] tracking-wider border-b border-zinc-900">
                      <tr>
                        <th className="px-6 py-4">Run ID</th>
                        <th className="px-6 py-4">Status</th>
                        <th className="px-6 py-4">Commit Hash</th>
                        <th className="px-6 py-4">Dataset</th>
                        <th className="px-6 py-4">Hyperparameters</th>
                        <th className="px-6 py-4 text-right">Metrics Summary</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-900 font-mono">
                      {runs.map(run => (
                        <tr 
                          key={run.id} 
                          onClick={() => setSelectedRun(run)}
                          className="hover:bg-zinc-900/30 cursor-pointer transition-colors"
                        >
                          <td className="px-6 py-4 font-bold text-white flex items-center gap-1.5">
                            <ChevronRight className="w-3.5 h-3.5 text-zinc-600" />
                            {run.id}
                          </td>
                          <td className="px-6 py-4">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              run.status === 'COMPLETED' ? 'bg-zinc-900 text-white border border-zinc-700' : 
                              run.status === 'FAILED' ? 'bg-black text-zinc-400 border border-zinc-800' : 
                              'bg-zinc-800 text-white border border-zinc-700 pulse-white'
                            }`}>{run.status}</span>
                          </td>
                          <td className="px-6 py-4 text-zinc-500">{run.git_commit}</td>
                          <td className="px-6 py-4 text-zinc-500">{run.dataset_version}</td>
                          <td className="px-6 py-4 text-zinc-500 max-w-[200px] truncate">{run.parameters}</td>
                          <td className="px-6 py-4 text-right text-white font-semibold">{run.metrics}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Tab: Run Monitor */}
          {activeTab === 'runs' && (
            <div className="flex flex-col gap-6">
              
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                
                {/* Console Output Terminal */}
                <div className="lg:col-span-2 flex flex-col gap-4">
                  <div className="glass rounded-2xl flex flex-col overflow-hidden border border-zinc-900">
                    
                    <div className="px-4 py-3 bg-zinc-900/50 border-b border-zinc-900 flex justify-between items-center">
                      <div className="flex items-center gap-2">
                        <Terminal className="w-4 h-4 text-white" />
                        <span className="text-xs font-bold text-white uppercase tracking-wider">Telemetry Logs Stream</span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-2.5 h-2.5 rounded-full bg-zinc-800"></span>
                        <span className="w-2.5 h-2.5 rounded-full bg-zinc-600"></span>
                        <span className="w-2.5 h-2.5 rounded-full bg-zinc-400"></span>
                      </div>
                    </div>

                    <pre className="bg-black p-4 font-mono text-xs text-zinc-200 h-96 overflow-y-auto leading-relaxed border-none terminal-scroll">
                      {consoleOutput}
                      {isSimulating && <span className="animate-pulse">_</span>}
                    </pre>
                  </div>
                </div>

                {/* Simulation Control center */}
                <div className="glass p-6 rounded-2xl flex flex-col gap-5 border border-zinc-900 h-fit">
                  <div>
                    <h3 className="text-md font-bold text-white flex items-center gap-2">
                      <Sliders className="w-4 h-4 text-white" />
                      Simulation Controls
                    </h3>
                    <p className="text-[11px] text-zinc-500 mt-0.5">Simulate dynamic execution and trigger cluster failure states.</p>
                  </div>
                  
                  <div className="flex flex-col gap-4 text-xs font-medium">
                    <div>
                      <label className="block text-[10px] text-zinc-400 uppercase font-bold tracking-wider mb-1.5">Model Architecture</label>
                      <select 
                        value={simModel} 
                        onChange={e => setSimModel(e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-white font-semibold font-mono focus:outline-none focus:border-zinc-700"
                      >
                        <option value="Transformer">Transformer (12-Layers)</option>
                        <option value="ResNet">ResNet-50</option>
                      </select>
                    </div>
                    
                    <div>
                      <label className="block text-[10px] text-zinc-400 uppercase font-bold tracking-wider mb-1.5">Batch Size</label>
                      <input 
                        type="number" 
                        value={simBatch} 
                        onChange={e => setSimBatch(Number(e.target.value))}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-white font-mono focus:outline-none focus:border-zinc-700"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-[10px] text-zinc-400 uppercase font-bold tracking-wider mb-1.5">Desired Run Outcome</label>
                      <select 
                        value={simFail ? 'true' : 'false'} 
                        onChange={e => setSimFail(e.target.value === 'true')}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-white font-semibold font-mono focus:outline-none focus:border-zinc-700"
                      >
                        <option value="false">Complete Successfully</option>
                        <option value="true">Trigger GPU CUDA OOM</option>
                      </select>
                    </div>
                    
                    <button 
                      onClick={handleSimulateRun}
                      disabled={isSimulating}
                      className="w-full py-3 bg-white hover:bg-zinc-200 disabled:opacity-50 text-black rounded-xl text-xs font-bold flex items-center justify-center gap-2 mt-2 transition glow-btn"
                    >
                      <Play className="w-3.5 h-3.5" /> Start Telemetry Simulator
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Tab: Workflows DAG */}
          {activeTab === 'workflows' && (
            <div className="flex flex-col gap-6">
              <div>
                <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                  <GitBranch className="w-5 h-5 text-white" />
                  DAG Pipelines
                </h2>
                <p className="text-xs text-zinc-500 font-medium">Review real-time pipelines and execution DAGs across Kubernetes nodes.</p>
              </div>

              <div className="glass rounded-2xl overflow-hidden border border-zinc-900 h-[480px]">
                <ReactFlow 
                  nodes={dagNodes} 
                  edges={dagEdges}
                  fitView
                >
                  <Background color="rgba(255,255,255,0.015)" gap={16} />
                  <Controls className="bg-zinc-900 border border-zinc-800 text-white fill-current" />
                </ReactFlow>
              </div>
            </div>
          )}

          {/* Tab: Scheduler */}
          {activeTab === 'scheduler' && (
            <div className="flex flex-col gap-6">
              
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                
                {/* Metrics Summary */}
                <div className="lg:col-span-2 flex flex-col gap-6">
                  <div className="glass p-6 rounded-2xl border border-zinc-900">
                    <h3 className="text-xs font-bold text-zinc-400 tracking-wider uppercase mb-5">GPU Memory consumption per Node</h3>
                    <div className="h-64">
                      <Bar 
                        data={chartsData.gpuNodeMemory} 
                        options={{
                          responsive: true,
                          maintainAspectRatio: false,
                          plugins: { legend: { display: false } },
                          scales: {
                            y: { grid: { color: 'rgba(255,255,255,0.015)' }, ticks: { color: '#71717a' } },
                            x: { grid: { display: false }, ticks: { color: '#71717a' } }
                          }
                        }} 
                      />
                    </div>
                  </div>
                </div>

                {/* Queue Benchmarks Card */}
                <div className="flex flex-col gap-6">
                  {/* Allocation Donut */}
                  <div className="glass p-6 rounded-2xl border border-zinc-900 flex flex-col items-center">
                    <h3 className="text-xs font-bold text-zinc-400 tracking-wider uppercase mb-5 self-start">Cluster GPU Allocation</h3>
                    <div className="w-40 h-40">
                      <Doughnut 
                        data={chartsData.gpuAllocation} 
                        options={{ cutout: '75%', plugins: { legend: { display: false } } }} 
                      />
                    </div>
                    <div className="text-center mt-4">
                      <p className="text-xl font-bold text-white font-mono">82%</p>
                      <p className="text-[10px] text-zinc-500 uppercase font-bold tracking-wide">Reserved capacity</p>
                    </div>
                  </div>

                  {/* Latency Benchmarks */}
                  <div className="glass p-5 rounded-2xl border border-zinc-900">
                    <h3 className="text-xs font-bold text-zinc-400 tracking-wider uppercase mb-3">Scheduling Optimization</h3>
                    <div className="flex flex-col gap-3 text-xs">
                      <div className="flex justify-between border-b border-zinc-900 pb-2 font-medium">
                        <span className="text-zinc-400">Queue Latency Reduction</span>
                        <span className="text-white font-bold font-mono">2.95x Faster</span>
                      </div>
                      <div className="flex justify-between border-b border-zinc-900 pb-2 font-medium">
                        <span className="text-zinc-400">GPU Idle Time</span>
                        <span className="text-white font-bold font-mono">5.8%</span>
                      </div>
                    </div>
                  </div>
                </div>

              </div>
            </div>
          )}

          {/* Tab: Lineage */}
          {activeTab === 'lineage' && (
            <div className="flex flex-col gap-6">
              <div>
                <h2 className="text-xl font-bold text-white tracking-tight flex items-center gap-2">
                  <Share2 className="w-5 h-5 text-white" />
                  Dataset Lineage
                </h2>
                <p className="text-xs text-zinc-500 font-medium">Track artifacts back to training databases and raw dataset logs.</p>
              </div>

              <div className="glass rounded-2xl overflow-hidden border border-zinc-900 h-[480px]">
                <ReactFlow 
                  nodes={lineageNodes} 
                  edges={lineageEdges}
                  fitView
                >
                  <Background color="rgba(255,255,255,0.015)" gap={16} />
                  <Controls className="bg-zinc-900 border border-zinc-800 text-white fill-current" />
                </ReactFlow>
              </div>
            </div>
          )}

          {/* Tab: Model Registry */}
          {activeTab === 'registry' && (
            <div className="flex flex-col gap-6">
              
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                
                {/* Model Catalog List */}
                <div className="glass p-5 rounded-2xl border border-zinc-900 flex flex-col gap-3 h-fit">
                  <h3 className="text-xs font-bold text-zinc-400 tracking-wider uppercase mb-3">Model Registry catalog</h3>
                  {models.map(m => (
                    <button
                      key={m.id}
                      onClick={() => setSelectedModel(m)}
                      className={`w-full text-left p-3.5 rounded-xl border transition-all ${
                        selectedModel?.id === m.id 
                          ? 'bg-zinc-900/60 border-zinc-700 shadow-md' 
                          : 'bg-zinc-900/20 border-zinc-900 hover:bg-zinc-900/40'
                      }`}
                    >
                      <div className="flex justify-between items-start">
                        <span className="text-xs font-bold text-white">{m.name}</span>
                        {m.production_version && (
                          <span className="bg-white text-black text-[8px] font-bold px-1.5 py-0.5 rounded-full">PROD</span>
                        )}
                      </div>
                      <p className="text-[10px] text-zinc-500 mt-1 line-clamp-1">{m.description || 'No description available.'}</p>
                    </button>
                  ))}
                </div>

                {/* Selected Model Versions */}
                <div className="lg:col-span-2 flex flex-col gap-6">
                  {selectedModel ? (
                    <div className="glass p-6 rounded-2xl border border-zinc-900 flex flex-col gap-5">
                      <div>
                        <span className="text-[10px] text-zinc-500 font-bold uppercase tracking-wider">Model Catalog details</span>
                        <h2 className="text-lg font-bold text-white mt-1">{selectedModel.name}</h2>
                        <p className="text-xs text-zinc-400 mt-1">{selectedModel.description}</p>
                      </div>

                      {/* Versions list */}
                      <div className="flex flex-col gap-4">
                        <h4 className="text-xs font-bold text-zinc-400 uppercase tracking-wider">Registered Versions</h4>
                        
                        <div className="flex flex-col gap-3">
                          {versions.map(v => (
                            <div key={v.id} className="bg-zinc-900/40 border border-zinc-800 rounded-xl p-4 flex flex-col gap-3.5">
                              
                              <div className="flex justify-between items-center">
                                <div className="flex items-center gap-3">
                                  <span className="text-xs font-bold text-white">{v.version}</span>
                                  <span className="text-[10px] text-zinc-500 font-mono">Run: {v.run_id}</span>
                                </div>
                                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  v.stage === 'PRODUCTION' ? 'bg-zinc-850 text-white border border-zinc-700' :
                                  v.stage === 'STAGING' ? 'bg-zinc-900 text-zinc-300 border border-zinc-800' :
                                  'bg-black text-zinc-400 border border-zinc-800'
                                }`}>{v.stage}</span>
                              </div>

                              <div className="text-[11px] text-zinc-500 font-mono flex flex-col gap-1 border-t border-zinc-900 pt-3">
                                <span>Artifact S3 URI: {v.artifact_uri}</span>
                                <span>Registered At: {new Date(v.created_at).toLocaleString()}</span>
                              </div>

                              {/* Approvals History Timeline */}
                              {v.history && v.history.length > 0 && (
                                <div className="flex flex-col gap-2.5 mt-2 bg-zinc-950/40 p-3 rounded-lg border border-zinc-900">
                                  <span className="text-[9px] text-zinc-400 uppercase font-bold tracking-wider flex items-center gap-1.5 font-mono">
                                    <History className="w-3 h-3 text-zinc-400" /> Stage Transition Logs
                                  </span>
                                  <div className="flex flex-col gap-2 border-l border-zinc-800 pl-3.5">
                                    {v.history.map((h: any, idx: number) => (
                                      <div key={idx} className="text-[10px] flex flex-col gap-0.5 relative">
                                        <div className="absolute -left-[19.5px] top-1.5 w-1.5 h-1.5 bg-zinc-700 rounded-full"></div>
                                        <div className="flex items-center gap-1.5 text-zinc-300 font-semibold">
                                          <span>{h.from_stage}</span>
                                          <span>→</span>
                                          <span className="text-white">{h.to_stage}</span>
                                        </div>
                                        <span className="text-[9px] text-zinc-500 font-mono">Approved by {h.approver} on {new Date(h.approved_at).toLocaleDateString()}</span>
                                        {h.notes && <p className="text-[10px] text-zinc-400 mt-1 italic font-sans border-l border-zinc-700 pl-2">"{h.notes}"</p>}
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              {/* Promotion trigger */}
                              <div className="flex gap-2 justify-end mt-1.5">
                                <button 
                                  onClick={() => setIsPromoting(v.id)}
                                  className="px-3 py-1.5 bg-zinc-900 hover:bg-zinc-800 text-white rounded-lg text-[10px] font-bold tracking-wide flex items-center gap-1 transition border border-zinc-800"
                                >
                                  <Plus className="w-3 h-3" /> Promote Stage
                                </button>
                              </div>

                            </div>
                          ))}
                        </div>
                      </div>

                    </div>
                  ) : (
                    <div className="glass p-12 rounded-2xl border border-zinc-900 flex flex-col items-center justify-center text-center gap-2">
                      <Package className="w-8 h-8 text-zinc-700" />
                      <p className="text-zinc-500 text-xs font-semibold">Select a model from the registry catalog to inspect its versions</p>
                    </div>
                  )}
                </div>

              </div>
            </div>
          )}

          {/* Tab: AI Failure Agent */}
          {activeTab === 'agent' && (
            <div className="flex flex-col gap-6">
              
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                
                {/* Select Run box */}
                <div className="glass p-6 rounded-2xl border border-zinc-900 flex flex-col gap-4 h-fit">
                  <div>
                    <h3 className="text-md font-bold text-white flex items-center gap-2">
                      <Sparkles className="w-4 h-4 text-white pulse-white" />
                      AI Diagnostic Agent
                    </h3>
                    <p className="text-[11px] text-zinc-500 mt-0.5 font-medium">Diagnose telemetry errors and CUDA allocation faults automatically.</p>
                  </div>
                  
                  <div className="flex flex-col gap-4 text-xs">
                    <div>
                      <label className="block text-[10px] text-zinc-400 uppercase font-bold tracking-wider mb-1.5">Select Failed Run</label>
                      <select 
                        value={agentRun} 
                        onChange={e => setAgentRun(e.target.value)}
                        className="w-full bg-zinc-950 border border-zinc-800 rounded-xl px-3 py-2 text-white font-semibold font-mono focus:outline-none"
                      >
                        <option value="">Select a run...</option>
                        {runs.filter(r=>r.status==='FAILED').map(r => (
                          <option key={r.id} value={r.id}>{r.id} (FAILED)</option>
                        ))}
                      </select>
                    </div>
                    
                    <button 
                      onClick={handleDiagnose}
                      disabled={!agentRun || agentLoading}
                      className="w-full py-3 bg-white hover:bg-zinc-200 disabled:opacity-50 text-black rounded-xl text-xs font-bold flex items-center justify-center gap-2 transition glow-btn"
                    >
                      <Sparkles className="w-3.5 h-3.5" /> Diagnose Logs & Telemetry
                    </button>
                  </div>
                </div>

                {/* Diagnostic Results Console */}
                <div className="lg:col-span-2 glass-premium p-6 rounded-2xl min-h-[360px] border border-zinc-900">
                  <h3 className="text-xs font-bold text-white border-b border-zinc-900 pb-3 mb-5 uppercase tracking-wider flex items-center gap-2">
                    <Terminal className="w-4 h-4 text-white" />
                    Diagnostic Report Summary
                  </h3>
                  
                  {agentLoading && (
                    <div className="flex flex-col items-center justify-center py-24 gap-3">
                      <div className="w-10 h-10 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                      <span className="text-xs text-zinc-500 font-mono tracking-wide">AI Agent scanning log files & cluster metrics...</span>
                    </div>
                  )}

                  {!agentLoading && agentResult && (
                    <div className="flex flex-col gap-5 text-xs">
                      <div className="bg-zinc-900 border border-zinc-800 p-4 rounded-xl text-white font-bold tracking-wide flex items-center gap-2 font-mono">
                        <AlertTriangle className="w-4 h-4 text-zinc-400" /> Category: {agentResult.failure_category}
                      </div>
                      
                      <div className="flex flex-col gap-1.5">
                        <p className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider">Root Cause Analysis</p>
                        <p className="text-white font-semibold leading-relaxed bg-zinc-900/40 p-3.5 rounded-xl border border-zinc-800 font-sans">{agentResult.root_cause}</p>
                      </div>
                      
                      <div className="flex flex-col gap-1.5">
                        <p className="text-[10px] text-zinc-500 uppercase font-bold tracking-wider">Detailed Explanation</p>
                        <p className="text-zinc-300 leading-relaxed font-sans">{agentResult.explanation}</p>
                      </div>
                      
                      <div className="bg-zinc-900 border border-zinc-800 p-4 rounded-xl flex flex-col gap-3">
                        <p className="text-white uppercase text-[10px] font-bold tracking-wider">Diagnostic Recommendations</p>
                        <ul className="list-disc pl-5 text-zinc-300 space-y-2 font-sans text-xs">
                          {agentResult.recommendations.map((rec: string, idx: number) => (
                            <li key={idx} className="leading-relaxed">{rec}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  )}

                  {!agentLoading && !agentResult && (
                    <div className="text-center py-24 text-zinc-600 text-xs flex flex-col items-center justify-center gap-2 font-medium">
                      <Info className="w-6 h-6 text-zinc-800" />
                      Select a failed run container from the sidebar diagnostics panel to trigger AI analysis.
                    </div>
                  )}
                </div>

              </div>
            </div>
          )}

        </main>
      </div>

      {/* Model Promotion Modal overlay */}
      {isPromoting && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-premium w-full max-w-md rounded-2xl overflow-hidden border border-zinc-800">
            <div className="p-5 border-b border-zinc-800 flex justify-between items-center bg-zinc-900/40">
              <span className="text-xs font-bold text-white uppercase tracking-wider font-mono">Promote Model Stage</span>
              <button onClick={() => setIsPromoting(null)} className="text-zinc-400 hover:text-white"><X className="w-4 h-4" /></button>
            </div>
            <div className="p-5 flex flex-col gap-4 text-xs font-medium">
              <div>
                <label className="block text-[10px] text-zinc-400 uppercase font-bold tracking-wider mb-1.5">Target Registry Stage</label>
                <select 
                  value={promotionStage} 
                  onChange={e => setPromotionStage(e.target.value as any)}
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-3 py-2.5 text-white font-semibold focus:outline-none"
                >
                  <option value="STAGING">STAGING</option>
                  <option value="PRODUCTION">PRODUCTION</option>
                  <option value="ARCHIVED">ARCHIVED</option>
                </select>
              </div>
              
              <div>
                <label className="block text-[10px] text-zinc-400 uppercase font-bold tracking-wider mb-1.5">Approval Notes</label>
                <textarea 
                  value={promotionNotes} 
                  onChange={e => setPromotionNotes(e.target.value)}
                  placeholder="Enter verification comments or audit details..."
                  className="w-full bg-zinc-900 border border-zinc-800 rounded-xl p-3 text-white h-24 focus:outline-none focus:border-zinc-700"
                />
              </div>

              <div className="flex gap-2.5 justify-end mt-2">
                <button 
                  onClick={() => setIsPromoting(null)}
                  className="px-4 py-2 border border-zinc-800 hover:bg-zinc-900 text-zinc-300 rounded-xl font-semibold transition"
                >
                  Cancel
                </button>
                <button 
                  onClick={handlePromote}
                  className="px-4 py-2 bg-white hover:bg-zinc-200 text-black rounded-xl font-bold transition"
                >
                  Confirm Promotion
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Sliding Metrics Drawer overlay */}
      {selectedRun && (
        <div className="fixed inset-y-0 right-0 z-50 w-full max-w-xl bg-black border-l border-zinc-900 shadow-2xl flex flex-col">
          <div className="p-5 border-b border-zinc-900 bg-zinc-950 flex justify-between items-center">
            <div>
              <span className="text-[10px] text-white font-bold uppercase tracking-wider font-mono">Metrics Inspector</span>
              <h3 className="text-sm font-bold text-white mt-0.5">Telemetry metrics: {selectedRun.id}</h3>
            </div>
            <button onClick={() => setSelectedRun(null)} className="p-1 rounded-lg bg-zinc-900 border border-zinc-800 text-zinc-400 hover:text-white transition">
              <X className="w-4 h-4" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-6 text-xs terminal-scroll">
            
            {/* Run details */}
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-zinc-900/40 border border-zinc-800 p-3.5 rounded-xl flex flex-col">
                <span className="text-[9px] text-zinc-500 uppercase font-bold tracking-wider">Dataset Code version</span>
                <span className="text-white font-mono mt-1 font-semibold">{selectedRun.dataset_version}</span>
              </div>
              <div className="bg-zinc-900/40 border border-zinc-800 p-3.5 rounded-xl flex flex-col">
                <span className="text-[9px] text-zinc-500 uppercase font-bold tracking-wider">Git Commit Hash</span>
                <span className="text-white font-mono mt-1 font-semibold">{selectedRun.git_commit}</span>
              </div>
            </div>

            {/* Hyperparameters list */}
            <div className="bg-zinc-900/20 border border-zinc-850 p-4 rounded-xl flex flex-col gap-2">
              <span className="text-[9px] text-zinc-500 uppercase font-bold tracking-wider mb-1">Hyperparameter Configuration</span>
              <div className="grid grid-cols-2 gap-2 text-xs font-mono">
                {selectedRun.parameters.split(',').map((p, idx) => {
                  const parts = p.trim().split(':')
                  return (
                    <div key={idx} className="flex justify-between border-b border-zinc-900 pb-1">
                      <span className="text-zinc-500">{parts[0]}</span>
                      <span className="text-white font-bold">{parts[1]}</span>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Live Chart plot */}
            {selectedRun.status === 'COMPLETED' ? (
              <div className="bg-zinc-900/40 border border-zinc-850 p-4 rounded-xl flex flex-col gap-3">
                <span className="text-[9px] text-zinc-500 uppercase font-bold tracking-wider">Loss vs. Accuracy plots (Training steps)</span>
                <div className="h-64 mt-2">
                  <Line 
                    data={chartsData.lossAcc} 
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      plugins: { legend: { labels: { color: '#a1a1aa', boxWidth: 12 }, position: 'bottom' } },
                      scales: {
                        y: { position: 'left', grid: { color: 'rgba(255,255,255,0.015)' }, ticks: { color: '#71717a' } },
                        y1: { position: 'right', grid: { display: false }, ticks: { color: '#71717a' } },
                        x: { grid: { display: false }, ticks: { color: '#71717a' } }
                      }
                    }} 
                  />
                </div>
              </div>
            ) : (
              <div className="bg-zinc-950 border border-zinc-900 p-12 rounded-xl flex flex-col items-center justify-center text-center gap-2">
                <AlertTriangle className="w-6 h-6 text-white" />
                <p className="text-zinc-500 text-xs font-medium">Run terminated pre-maturely. Telemetry chart data is incomplete or corrupted.</p>
                <button 
                  onClick={() => {
                    setAgentRun(selectedRun.id)
                    setActiveTab('agent')
                    setSelectedRun(null)
                  }}
                  className="px-4 py-2 bg-zinc-900 hover:bg-zinc-850 text-white border border-zinc-800 rounded-xl text-[10px] font-bold tracking-wide mt-2 transition"
                >
                  Diagnose with Failure Agent
                </button>
              </div>
            )}

            {/* Telemetry log list */}
            <div className="flex flex-col gap-2">
              <span className="text-[9px] text-zinc-500 uppercase font-bold tracking-wider">Console telemetry cache</span>
              <pre className="bg-black p-4 rounded-xl font-mono text-[10px] text-zinc-200 h-32 overflow-y-auto leading-relaxed border border-zinc-900 terminal-scroll">
                {selectedRun.status === 'COMPLETED' ? (
                  `[SYSTEM] Run complete.\n[RUNNER] Uploading checkpoints to S3 bucket...\n[SYSTEM] Checkpoint verified: Acc=0.985.`
                ) : (
                  `[ERROR] CUDA Out of Memory (OOM). Tried to allocate 4.20 GiB.\n[SYSTEM] Telemetry channel aborted.\n[SYSTEM] Container exit code: 1.`
                )}
              </pre>
            </div>

          </div>
        </div>
      )}

    </div>
  )
}
