"""
Synthetic healthcare RCM dataset generator.

Builds the 7 CSV files used by the Power BI dashboard (fact_claims, fact_ar_followup,
dim_payer, dim_provider, dim_denial_reason, dim_cpt, dim_agent).

Stage 1: base claims, payers, providers, denial reasons, follow-up actions
Stage 2: age the AR (some old denials and slow-payer claims stay unresolved)
Stage 3: make sure no payment date falls after the snapshot date

Usage:  python generate_rcm_data.py [output_folder]      (default: ./data)
Snapshot date: 2026-09-30. All data is synthetic.
"""
import os, shutil, sys, tempfile
import numpy as np, pandas as pd

SNAP = pd.Timestamp("2026-09-30")


def stage1(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(42)
    SNAP = pd.Timestamp("2026-09-30")

    payer = pd.DataFrame([
     (1,"Medicare","Government",0.07,28),(2,"Medicaid","Government",0.11,42),
     (3,"Aetna","Commercial",0.10,30),(4,"UnitedHealthcare","Commercial",0.14,35),
     (5,"Cigna","Commercial",0.12,33),(6,"Blue Cross Blue Shield","Commercial",0.09,27),
     (7,"Humana","Medicare Advantage",0.13,36),(8,"Self-Pay","Self-Pay",0.02,60)],
     columns=["payer_id","payer_name","payer_type","denial_rate","avg_days_to_pay"])

    provider = pd.DataFrame([
     (101,"Dr. Anand Rao","Internal Medicine","Primary Care"),(102,"Dr. Meera Iyer","Cardiology","Specialty"),
     (103,"Dr. Karthik Nair","Orthopedics","Surgery"),(104,"Dr. Priya Menon","Radiology","Diagnostics"),
     (105,"Dr. Suresh Babu","Emergency Medicine","Emergency"),(106,"Dr. Lakshmi Devi","Pediatrics","Primary Care"),
     (107,"Dr. Arjun Patel","Oncology","Specialty"),(108,"Dr. Neha Kapoor","Gastroenterology","Specialty")],
     columns=["provider_id","provider_name","specialty","department"])

    denial = pd.DataFrame([
     ("CO-4","Procedure code inconsistent with modifier","Coding",1,0.10),
     ("CO-16","Claim lacks information / billing error","Billing",1,0.22),
     ("CO-18","Duplicate claim","Billing",1,0.06),
     ("CO-27","Coverage terminated before service","Eligibility",1,0.09),
     ("CO-29","Timely filing limit expired","Timely Filing",1,0.05),
     ("CO-50","Not medically necessary","Medical Necessity",0,0.14),
     ("CO-97","Bundled / included in another service","Coding",1,0.09),
     ("CO-197","Prior authorization absent","Authorization",1,0.17),
     ("PR-1","Deductible amount (patient responsibility)","Patient Responsibility",0,0.08)],
     columns=["denial_code","denial_description","denial_category","preventable","weight"])
    denial["weight"]=denial["weight"]/denial["weight"].sum()

    cpt = {"99213":(130,"E/M"),"99214":(190,"E/M"),"93000":(95,"Cardio"),"93306":(450,"Cardio"),
     "73721":(900,"Imaging"),"72148":(1200,"Imaging"),"27447":(14500,"Surgery"),"29881":(6800,"Surgery"),
     "45378":(1800,"Procedure"),"96413":(2400,"Chemo"),"99285":(1100,"ED"),"99391":(210,"Preventive")}
    cpt_df = pd.DataFrame([(k,v[1],v[0]) for k,v in cpt.items()],columns=["cpt_code","cpt_category","base_charge"])
    cpt_codes=list(cpt)

    N=12000
    dos = pd.to_datetime("2025-01-01")+pd.to_timedelta(rng.integers(0,(pd.Timestamp("2026-09-15")-pd.Timestamp("2025-01-01")).days,N),unit="D")
    pay_w = np.array([.22,.10,.13,.17,.11,.15,.08,.04])
    payer_id = rng.choice(payer.payer_id,N,p=pay_w)
    prov_id = rng.choice(provider.provider_id,N,p=[.2,.14,.1,.12,.16,.1,.08,.1])
    cpt_c = rng.choice(cpt_codes,N)
    charge = np.array([cpt[c][0] for c in cpt_c])*rng.uniform(0.9,1.15,N)
    charge = charge.round(2)
    sub_lag = rng.choice([1,2,3,5,7,10,14,21,35],N,p=[.2,.2,.18,.15,.1,.08,.05,.03,.01])
    sub = dos+pd.to_timedelta(sub_lag,unit="D")
    sub = sub.where(sub<=SNAP, SNAP)

    pm = payer.set_index("payer_id")
    den_rate = pm.loc[payer_id,"denial_rate"].values + np.where(sub_lag>=21,0.10,0)
    is_denied = rng.random(N)<den_rate
    dcodes = rng.choice(denial.denial_code,N,p=denial.weight)
    allowed_pct = np.where(pm.loc[payer_id,"payer_type"].values=="Government",0.45,
                  np.where(pm.loc[payer_id,"payer_type"].values=="Self-Pay",0.70,0.62))*rng.uniform(.9,1.1,N)
    allowed = (charge*allowed_pct).round(2)
    pat_resp = np.where(pm.loc[payer_id,"payer_type"].values=="Self-Pay",allowed,
               (allowed*rng.choice([0,.05,.1,.2],N,p=[.35,.3,.25,.1]))).round(2)
    days_to_pay = np.maximum(3,(pm.loc[payer_id,"avg_days_to_pay"].values*rng.uniform(.6,1.6,N))).astype(int)
    pay_date = sub+pd.to_timedelta(days_to_pay,unit="D")

    status=[];paid=[];pdate=[];dc=[];appeal=[];recov=[]
    for i in range(N):
        if is_denied[i]:
            dc.append(dcodes[i])
            # appeal outcome
            if sub[i]+pd.Timedelta(days=60)>SNAP:
                status.append("Denied - In Appeal" if rng.random()<.5 else "Denied"); paid.append(0.0); pdate.append(pd.NaT); appeal.append(status[-1]=="Denied - In Appeal"); recov.append(0.0)
            else:
                denial_preventable = denial.set_index("denial_code").loc[dcodes[i],"preventable"]
                if rng.random()<(0.55 if denial_preventable else 0.25):
                    status.append("Paid After Appeal"); amt=round((allowed[i]-pat_resp[i])*rng.uniform(.8,1.0),2)
                    paid.append(amt); pdate.append(sub[i]+pd.Timedelta(days=int(rng.integers(45,100)))); appeal.append(True); recov.append(amt)
                else:
                    status.append("Denied - Written Off"); paid.append(0.0); pdate.append(pd.NaT); appeal.append(bool(rng.random()<.4)); recov.append(0.0)
        else:
            dc.append(None)
            if pay_date[i]<=SNAP:
                status.append("Paid"); paid.append(round(allowed[i]-pat_resp[i],2)); pdate.append(pay_date[i]); appeal.append(False); recov.append(0.0)
            else:
                status.append("Pending"); paid.append(0.0); pdate.append(pd.NaT); appeal.append(False); recov.append(0.0)

    claims = pd.DataFrame({
     "claim_id":[f"CLM{100000+i}" for i in range(N)],
     "patient_id":[f"PT{rng.integers(1000,5200)}" for _ in range(N)],
     "provider_id":prov_id,"payer_id":payer_id,"cpt_code":cpt_c,
     "date_of_service":dos.date,"submission_date":sub.date,
     "charge_amount":charge,"allowed_amount":allowed,"patient_responsibility":pat_resp,
     "paid_amount":paid,"payment_date":pd.to_datetime(pdate).date if False else pdate,
     "claim_status":status,"denial_code":dc,"appealed":appeal,
    })
    claims["payment_date"]=pd.to_datetime(claims["payment_date"]).dt.date
    # first-pass: submitted clean & not denied
    claims["first_pass_flag"]=(~is_denied).astype(int)
    claims["adjustment_amount"]=np.where(claims.claim_status.isin(["Paid","Paid After Appeal"]),(charge-allowed).round(2),0.0)
    claims["writeoff_amount"]=np.where(claims.claim_status=="Denied - Written Off",allowed,0.0).round(2)

    # AR follow-up actions for unpaid/denied claims
    agents=pd.DataFrame([(f"A{n}",nm) for n,nm in enumerate(["Gokul S","Divya R","Ramesh K","Swathi M","Vignesh P","Anitha L"],1)],columns=["agent_id","agent_name"])
    rows=[]
    unresolved=claims[claims.claim_status.isin(["Pending","Denied","Denied - In Appeal","Denied - Written Off","Paid After Appeal"])]
    for _,r in unresolved.iterrows():
        n=rng.integers(1,4)
        base=pd.Timestamp(r.submission_date)
        for k in range(n):
            d=base+pd.Timedelta(days=int(rng.integers(15,40))*(k+1))
            if d>SNAP: break
            act=rng.choice(["Called Payer","Portal Check","Appeal Filed","Corrected Claim Sent","Records Submitted","Escalated"],p=[.35,.2,.15,.12,.1,.08])
            out=rng.choice(["Promise to Pay","Reprocessing","Denial Upheld","No Response","Claim Paid","Needs Documentation"],p=[.2,.25,.12,.18,.1,.15])
            rows.append((r.claim_id,d.date(),rng.choice(agents.agent_id),act,out,int(rng.integers(4,25))))
    followup=pd.DataFrame(rows,columns=["claim_id","action_date","agent_id","action_type","outcome","minutes_spent"])
    followup.insert(0,"action_id",[f"ACT{200000+i}" for i in range(len(followup))])

    out=out_dir.rstrip("/")+"/"
    payer.drop(columns=["denial_rate"]).to_csv(out+"dim_payer.csv",index=False)
    provider.to_csv(out+"dim_provider.csv",index=False)
    denial.drop(columns=["weight"]).to_csv(out+"dim_denial_reason.csv",index=False)
    cpt_df.to_csv(out+"dim_cpt.csv",index=False)
    agents.to_csv(out+"dim_agent.csv",index=False)
    claims.to_csv(out+"fact_claims.csv",index=False)
    followup.to_csv(out+"fact_ar_followup.csv",index=False)


def stage2(src_dir, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    for f in ["dim_agent", "dim_cpt", "dim_denial_reason", "dim_payer", "dim_provider"]:
        shutil.copy(os.path.join(src_dir, f + ".csv"), os.path.join(out_dir, f + ".csv"))
    src_dir = src_dir.rstrip("/") + "/"
    out_dir = out_dir.rstrip("/") + "/"
    SNAP = pd.Timestamp("2026-09-30")
    rng=np.random.default_rng(7)
    SNAP=pd.Timestamp("2026-09-30")
    c=pd.read_csv(src_dir+"fact_claims.csv")
    cols=list(c.columns)
    c["_sub"]=pd.to_datetime(c.submission_date)
    c["_dout"]=(SNAP-c["_sub"]).dt.days

    # A) some old written-off denials were never really closed -> still open (aged denials / long appeals)
    wo=c[(c.claim_status=="Denied - Written Off")&(c._dout<=270)].index
    pick=rng.choice(wo,int(len(wo)*0.45),replace=False)
    half=len(pick)//2
    den_idx,app_idx=pick[:half],pick[half:]
    c.loc[den_idx,["claim_status","appealed","writeoff_amount"]]=["Denied",False,0.0]
    c.loc[app_idx,["claim_status","appealed","writeoff_amount"]]=["Denied - In Appeal",True,0.0]

    # B) slow payers: some older, clean claims still unpaid (heavier for slow payers, tapering with age)
    slow={4,7,2,5}
    for i in c[(c.claim_status=="Paid")&(c._dout>=61)&(c._dout<=240)].index:
        dd=c.at[i,"_dout"]; sp=c.at[i,"payer_id"] in slow
        p=(.22 if sp else .07) if dd<=120 else ((.14 if sp else .04))
        if rng.random()<p:
            c.loc[i,["claim_status","paid_amount","payment_date","adjustment_amount"]]=["Pending",0.0,np.nan,0.0]
    c=c[cols]
    c.to_csv(out_dir+"fact_claims.csv",index=False)

    # follow-up actions regenerated for all unresolved / worked claims
    agents=pd.read_csv(src_dir+"dim_agent.csv")
    rows=[]
    work=c[c.claim_status.isin(["Pending","Denied","Denied - In Appeal","Denied - Written Off","Paid After Appeal"])]
    for _,r in work.iterrows():
        n=int(rng.integers(1,4)) if r.claim_status!="Pending" else int(rng.integers(1,4))
        base=pd.Timestamp(r.submission_date)
        for k in range(n):
            d=base+pd.Timedelta(days=int(rng.integers(15,40))*(k+1))
            if d>SNAP: break
            act=rng.choice(["Called Payer","Portal Check","Appeal Filed","Corrected Claim Sent","Records Submitted","Escalated"],p=[.35,.2,.15,.12,.1,.08])
            out=rng.choice(["Promise to Pay","Reprocessing","Denial Upheld","No Response","Claim Paid","Needs Documentation"],p=[.2,.25,.12,.18,.1,.15])
            rows.append((r.claim_id,d.date(),rng.choice(agents.agent_id),act,out,int(rng.integers(4,25))))
    f=pd.DataFrame(rows,columns=["claim_id","action_date","agent_id","action_type","outcome","minutes_spent"])
    f.insert(0,"action_id",[f"ACT{200000+i}" for i in range(len(f))])
    f.to_csv(out_dir+"fact_ar_followup.csv",index=False)



def stage3(out_dir):
    path = os.path.join(out_dir, "fact_claims.csv")
    c = pd.read_csv(path)
    sub = pd.to_datetime(c.submission_date)
    pay = pd.to_datetime(c.payment_date)
    rng = np.random.default_rng(11)
    for i in c.index[pay > SNAP]:
        lo = sub[i] + pd.Timedelta(days=45)
        hi = min(sub[i] + pd.Timedelta(days=100), SNAP)
        c.at[i, "payment_date"] = (lo + pd.Timedelta(days=int(rng.integers(0, (hi - lo).days + 1)))).date().isoformat()
    c.to_csv(path, index=False)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "data"
    with tempfile.TemporaryDirectory() as tmp:
        stage1(tmp)
        stage2(tmp, out)
    stage3(out)
    print("Done. Files written to", os.path.abspath(out))
