// Count indexed reads and source-span methods so equivalent rescanning strategies are visible.
export function countedSource(source, work) {
  return new Proxy(new String(source), {get(target,key) {
    if (typeof key==='string' && /^[0-9]+$/.test(key)) work(1);
    const value=Reflect.get(target,key,target);
    if(typeof value!=='function') return value;
    return (...args)=>{
      if(['slice','substring','substr'].includes(key)) {
        const start=Math.max(0,Number(args[0]??0));
        const end=key==='substr'?Math.min(source.length,start+Number(args[1]??source.length)):Math.min(source.length,Number(args[1]??source.length));
        work(Math.max(0,end-start));
      } else if(['split','indexOf','lastIndexOf','includes','match','matchAll','replace','replaceAll'].includes(key)) work(source.length);
      else if(['charAt','charCodeAt','codePointAt'].includes(key)) work(1);
      return Reflect.apply(value,target,args);
    };
  }});
}
