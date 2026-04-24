/* Moteur de calcul Outscale — sans dépendance UI */
window.OSCalc = (() => {

  const GROUPS = [
    {id:"compute",          label:"Puissance de calcul",      bc:"b-comp"},
    {id:"dedicated-access", label:"Acces Dedicated",          bc:"b-ded"},
    {id:"gpu",              label:"GPU flexible",             bc:"b-gpu"},
    {id:"oks",              label:"Kubernetes Control Plane", bc:"b-oks"},
    {id:"bsu",              label:"Stockage bloc (BSU)",      bc:"b-bsu"},
    {id:"oos",              label:"Stockage objet (OOS)",     bc:"b-oos"},
    {id:"net",              label:"Reseau",                   bc:"b-net"},
    {id:"lic",              label:"Licences",                 bc:"b-lic"},
  ];

  const BLABELS = {compute:"Compute","dedicated-access":"Dedicated",gpu:"GPU",oks:"OKS",bsu:"BSU",oos:"OOS",net:"Reseau",lic:"Licence"};
  const BCLS    = {compute:"b-comp","dedicated-access":"b-ded",gpu:"b-gpu",oks:"b-oks",bsu:"b-bsu",oos:"b-oos",net:"b-net",lic:"b-lic"};
  const FLAG    = {FR:"🇫🇷",US:"🇺🇸",JP:"🇯🇵"};
  const HPM     = 730;

  const UID = () => Math.random().toString(36).slice(2, 10);
  const fE  = (v, d=0) => (v||0).toLocaleString("fr-FR", {minimumFractionDigits:d, maximumFractionDigits:d}) + " EUR";
  const fp  = (v, d=4) => parseFloat((v||0).toFixed(d));

  const CPUGENS  = ["v1","v2","v3","v4","v5","v6","v7"];
  const PERF_OPTS = [{v:"medium",l:"medium (p3)"},{v:"high",l:"high (p2)"},{v:"highest",l:"highest (p1)"}];
  const NET_OPTS  = [
    "VPN IPsec","LBU ( / h)","EIP ( / h)","NAT gateway ( / h)",
    "DirectLink 1 Gb/s (par mois)","DirectLink 10 Gb/s (par mois)",
    "DirectLink - frais de mise en service","Hosted DirectLink - frais de mise en service",
    "Hosted DirectLink 1 Gb/s (par mois)","Hosted DirectLink 10 Gb/s (par mois)",
  ];

  const DEMO = [
    // EU-W2 — site principal
    {id:UID(),region_id:"eu-west-2",type:"compute",desc:"VM inference v10",qty:1,cpu_gen:"v7",vcore:126,ram:1024,perf:"highest",engagement:"ri-1y-upfront",dedicated:false,usage:1},
    {id:UID(),region_id:"eu-west-2",type:"compute",desc:"Web tier",qty:1,cpu_gen:"v7",vcore:4,ram:16,perf:"high",engagement:"on-demand",dedicated:false,usage:1},
    {id:UID(),region_id:"eu-west-2",type:"compute",desc:"Worker pool",qty:3,cpu_gen:"v7",vcore:2,ram:4,perf:"medium",engagement:"on-demand",dedicated:false,usage:1},
    {id:UID(),region_id:"eu-west-2",type:"compute",desc:"SGBD + BSU gp2",qty:1,cpu_gen:"v7",vcore:2,ram:4,perf:"high",engagement:"on-demand",dedicated:false,usage:1,storage_type:"BSU Performance (gp2)",storage_gb:500,iops:0},
    {id:UID(),region_id:"eu-west-2",type:"dedicated-access",desc:"Acces FCU Dedicated",qty:1,engagement:"on-demand",usage:1},
    {id:UID(),region_id:"eu-west-2",type:"oks",desc:"OKS Control Plane HA",qty:1,cp:"cp.3.masters.small",engagement:"on-demand",usage:1},
    {id:UID(),region_id:"eu-west-2",type:"gpu",desc:"GPU inference H100",gpu_qty:1,gpu_type:"Nvidia H100",engagement:"on-demand",usage:1},
    {id:UID(),region_id:"eu-west-2",type:"bsu",desc:"BSU Performance",qty:1,storage_type:"BSU Performance (gp2)",storage_gb:1500,iops:0},
    {id:UID(),region_id:"eu-west-2",type:"bsu",desc:"Snapshots",qty:1,storage_type:"Snapshots",storage_gb:3000,iops:0},
    {id:UID(),region_id:"eu-west-2",type:"oos",desc:"Stockage objet OOS",storage_gb:150},
    {id:UID(),region_id:"eu-west-2",type:"lic",desc:"Windows Server",lic_type:"Windows Server 2019/2022 (pack 2 coeurs - jusqu'a 2 VMs)",lic_qty:4},
    {id:UID(),region_id:"eu-west-2",type:"net",desc:"VPN IPsec",net_type:"VPN IPsec",net_qty:1},
    {id:UID(),region_id:"eu-west-2",type:"net",desc:"Load balancer",net_type:"LBU ( / h)",net_qty:1},
    // US-W1 — site de reprise d'activité
    {id:UID(),region_id:"us-west-1",type:"compute",desc:"App front HA (DR)",qty:2,cpu_gen:"v7",vcore:4,ram:16,perf:"high",engagement:"on-demand",dedicated:false,usage:0.5},
    {id:UID(),region_id:"us-west-1",type:"gpu",desc:"Ferme GPU H200 (US)",gpu_qty:4,gpu_type:"Nvidia H200",engagement:"ri-1y-upfront",usage:1},
    {id:UID(),region_id:"us-west-1",type:"bsu",desc:"BSU Magnetic (DR)",qty:2,storage_type:"BSU Magnetic (standard)",storage_gb:300,iops:0},
    {id:UID(),region_id:"us-west-1",type:"net",desc:"EIP (US)",net_type:"EIP ( / h)",net_qty:2},
  ];

  /* regions  : array of {id, flag, short, name}
     engagements : array of {id, label, discount} */
  function calcLine(line, C, regionId, regions, engagements) {
    const ri   = Math.max(0, regions.findIndex(r => r.id === regionId));
    const eng  = engagements.find(e => e.id === (line.engagement || "on-demand")) || engagements[0];
    const disc = eng.discount ?? eng.d ?? 0;
    const hpm  = C.hours_per_month || HPM;
    const usage = parseFloat(line.usage ?? 1) || 1;
    let monthly = 0, detail = "", group = line.type, setup = 0;

    switch (line.type) {
      case "compute": {
        const vt  = C.vcore[line.cpu_gen] || C.vcore.v7;
        const vcUO = (vt[line.perf || "high"] || vt.high)[ri] || 0;
        const ded  = line.dedicated ? (1 + (C.dedicated_surcharge || 0.10)) : 1.0;
        let stoM   = 0;
        if (line.storage_type && Number(line.storage_gb) > 0) {
          const s = C.storage[line.storage_type];
          if (s) stoM = ((s.gb[ri]||0) * Number(line.storage_gb) + (s.iops[ri]||0) * Number(line.iops||0)) * Number(line.qty||1);
        }
        monthly = (Number(line.vcore||0)*vcUO + Number(line.ram||0)*(C.ram[ri]||0)) * Number(line.qty||1) * hpm * usage * (1-disc) * ded + stoM;
        detail  = `${line.qty}x${line.vcore}vC.${line.ram}GiB ${line.cpu_gen}/${line.perf}` + (line.dedicated?" ded":"") + ` ${eng.label}`;
        break;
      }
      case "dedicated-access":
        monthly = (C.ded_fee[ri]||0) * hpm * Number(line.qty||1) * usage * (1-disc);
        detail  = `${line.qty}x acces dedicated ${fE(C.ded_fee[ri]||0,3)}/h`;
        break;
      case "gpu": {
        const pa    = C.gpu[line.gpu_type];
        const p     = pa ? (pa[ri]||0) : 0;
        const gpuCap = C.gpu_ri_cap ?? 0.30;
        const gDisc = Math.min(disc, gpuCap);
        monthly = p * Number(line.gpu_qty||0) * hpm * usage * (1-gDisc);
        detail  = `${line.gpu_qty}x${line.gpu_type}` + (disc > gpuCap ? ` cap${Math.round(gpuCap*100)}%` : "") + ` ${eng.label}`;
        break;
      }
      case "oks": {
        const p = (C.oks[line.cp] || C.oks["cp.3.masters.small"])[ri] || 0;
        monthly = p * hpm * Number(line.qty||1) * usage * (1-disc);
        detail  = `${line.qty}x${line.cp}`;
        break;
      }
      case "bsu": {
        const s = C.storage[line.storage_type] || C.storage["BSU Magnetic (standard)"];
        monthly = ((s.gb[ri]||0)*Number(line.storage_gb||0) + (s.iops[ri]||0)*Number(line.iops||0)) * Number(line.qty||1);
        detail  = `${line.qty}x${line.storage_gb}GiB ${line.storage_type}`;
        break;
      }
      case "oos":
        monthly = (C.oos.gb[ri]||0) * Number(line.storage_gb||0);
        detail  = `${line.storage_gb}GiB`;
        break;
      case "net": {
        const t = line.net_type || "", q = Number(line.net_qty||0);
        if      (t.startsWith("VPN"))      monthly = (C.vpn[ri]||0)*q*hpm;
        else if (t.startsWith("LBU"))      monthly = (C.lbu[ri]||0)*q*hpm;
        else if (t.startsWith("EIP"))      monthly = (C.eip[ri]||0)*q*hpm;
        else if (t.startsWith("NAT"))      monthly = (C.nat[ri]||0)*q*hpm;
        else if (t==="DirectLink 1 Gb/s (par mois)")    monthly = (C.dl_1gbps[ri]||0)*q;
        else if (t==="DirectLink 10 Gb/s (par mois)")   monthly = (C.dl_10gbps[ri]||0)*q;
        else if (t==="DirectLink - frais de mise en service")       { setup=(C.dl_setup[ri]||0)*q; monthly=0; }
        else if (t==="Hosted DirectLink - frais de mise en service"){ setup=(C.hdl_setup[ri]||0)*q; monthly=0; }
        else if (t==="Hosted DirectLink 1 Gb/s (par mois)")  monthly = (C.hdl_1gbps[ri]||0)*q;
        else if (t==="Hosted DirectLink 10 Gb/s (par mois)") monthly = (C.hdl_10gbps[ri]||0)*q;
        detail = `${q>0?q+"x":""}${t}`;
        break;
      }
      case "lic": {
        const l = C.lic[line.lic_type]; if (!l) break;
        const p = l.price[ri]||0, f = l.base==="h"?hpm:(l.base==="m"?1:1/12);
        monthly = p * f * Number(line.lic_qty||0);
        detail  = `${line.lic_qty}x${line.lic_type}`;
        break;
      }
    }
    return { group, monthly, yearly: monthly*12+setup, three_year: (monthly*12+setup)*3-setup*2, setup, detail };
  }

  return { GROUPS, BLABELS, BCLS, FLAG, HPM, UID, fE, fp, CPUGENS, PERF_OPTS, NET_OPTS, DEMO, calcLine };
})();
