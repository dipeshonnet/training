// EditorJS bridge copied into the pinned LMS frontend during the image build.
export class AICoach {
  constructor({data,readOnly}) {
    this.data={
      version:typeof data?.version==='string'?data.version.trim():'',
      channels:Array.isArray(data?.channels)?[...new Set(data.channels.filter(channel=>['workflow','chat','voice'].includes(channel)))]:[],
    }
    this.readOnly=readOnly
  }
  static get toolbox(){return {title:'AI Coach',icon:'<svg viewBox="0 0 24 24" width="18" height="18"><path d="M4 4h16v12H9l-5 4z" fill="none" stroke="currentColor"/></svg>'}}
  static get isReadOnlySupported(){return true}
  render(){
    const wrapper=document.createElement('section')
    if(this.readOnly){
      const heading=document.createElement('strong');heading.textContent='AI Coach assessment activity'
      const text=document.createElement('p');text.textContent='Open your assigned learning to start walkthrough, practice or assessment.'
      const link=document.createElement('a');link.href='/coach';link.textContent='Open AI Coach';link.className='text-ink-gray-9 underline'
      wrapper.append(heading,text,link)
    }else{
      const label=document.createElement('label');label.textContent='Published AI Coach version ID'
      const input=document.createElement('input');input.value=this.data.version||'';input.placeholder='Copy the version ID from Scenario Studio';input.className='w-full border rounded p-2';input.addEventListener('input',()=>this.data.version=input.value.trim());label.append(input);wrapper.append(label)
      const channelLabel=document.createElement('p');channelLabel.textContent='Required assessment channels';wrapper.append(channelLabel)
      for(const channel of ['workflow','chat','voice']){const l=document.createElement('label'),checkbox=document.createElement('input');checkbox.type='checkbox';checkbox.checked=(this.data.channels||[]).includes(channel);checkbox.addEventListener('change',()=>{const channels=new Set(this.data.channels||[]);checkbox.checked?channels.add(channel):channels.delete(channel);this.data.channels=[...channels]});l.append(checkbox,document.createTextNode(' '+channel+' '));wrapper.append(l)}
    }
    return wrapper
  }
  save(){return {version:this.data.version,channels:[...this.data.channels]}}
  validate(data){return Boolean(typeof data?.version==='string'&&data.version.trim()&&Array.isArray(data.channels)&&data.channels.length&&data.channels.every(channel=>['workflow','chat','voice'].includes(channel)))}
}
