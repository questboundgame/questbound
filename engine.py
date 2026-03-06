"""
QuestBound Engine v0.3
- Mestre responde perguntas dos PCs
- PCs usam Haiku (economia)
- Mestre usa Sonnet (qualidade narrativa)
"""

import random, json, os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# ================================================================
# CONFIG — Model Routing
# ================================================================
MODELO_MESTRE = "claude-sonnet-4-20250514"   # Narrativa precisa de qualidade
MODELO_PC = "claude-haiku-4-5-20251001"       # PCs: personalidade em respostas curtas

# ================================================================
# REGRAS
# ================================================================
class Tier(Enum):
    FORTE = "forte"; PARCIAL = "parcial"; FALHA = "falha"

class Stat(Enum):
    FORCA = "forca"; DESTREZA = "destreza"; INTELECTO = "intelecto"
    CORACAO = "coracao"; SOMBRA = "sombra"

STAT_NOME = {Stat.FORCA:"Força", Stat.DESTREZA:"Destreza", Stat.INTELECTO:"Intelecto",
             Stat.CORACAO:"Coração", Stat.SOMBRA:"Sombra"}

@dataclass
class Dado:
    d1:int; d2:int; mod:int; total:int; tier:Tier; stat:Stat; quem:str
    def __str__(self):
        lb = {Tier.FORTE:"⚔️ ACERTO FORTE!", Tier.PARCIAL:"⚡ ACERTO PARCIAL", Tier.FALHA:"💀 FALHA"}
        return (f"🎲 {self.quem} rola: [{self.d1}]+[{self.d2}]={self.d1+self.d2} "
                f"(+{self.mod} {STAT_NOME[self.stat]}) = {self.total} → {lb[self.tier]}")

@dataclass
class Stats:
    forca:int=0; destreza:int=0; intelecto:int=0; coracao:int=0; sombra:int=0
    pv:int=10; pv_max:int=10
    def get(self, s):
        return {Stat.FORCA:self.forca, Stat.DESTREZA:self.destreza,
                Stat.INTELECTO:self.intelecto, Stat.CORACAO:self.coracao,
                Stat.SOMBRA:self.sombra}[s]

def rolar(stat, stats, quem=""):
    d1,d2 = random.randint(1,6), random.randint(1,6)
    m = stats.get(stat); t = d1+d2+m
    tier = Tier.FORTE if t>=10 else (Tier.PARCIAL if t>=7 else Tier.FALHA)
    return Dado(d1,d2,m,t,tier,stat,quem)

GUIAS = {
    "atacar":     {Tier.FORTE:"Golpe certeiro com vantagem.",    Tier.PARCIAL:"Acerta mas se expõe.",     Tier.FALHA:"Erra. Inimigo reage."},
    "defender":   {Tier.FORTE:"Defesa perfeita.",                Tier.PARCIAL:"Absorve com dano parcial.",Tier.FALHA:"Defesa falha."},
    "furtividade":{Tier.FORTE:"Invisível.",                      Tier.PARCIAL:"Quase oculto.",            Tier.FALHA:"Visto."},
    "investigar": {Tier.FORTE:"Descobre tudo.",                  Tier.PARCIAL:"Info incompleta.",          Tier.FALHA:"Nada ou enganoso."},
    "persuadir":  {Tier.FORTE:"Convencido.",                     Tier.PARCIAL:"Quer algo em troca.",      Tier.FALHA:"Não compra."},
    "enganar":    {Tier.FORTE:"Acredita.",                       Tier.PARCIAL:"Desconfia.",               Tier.FALHA:"Viu a mentira."},
    "magia":      {Tier.FORTE:"Perfeita.",                       Tier.PARCIAL:"Efeito colateral.",        Tier.FALHA:"Sai do controle."},
}

PC_STATS = {
    "kael":   Stats(forca=-1, destreza=2, intelecto=1, coracao=0, sombra=2, pv=8, pv_max=8),
    "sera":   Stats(forca=1,  destreza=-1,intelecto=2, coracao=2, sombra=0, pv=10,pv_max=10),
    "thorne": Stats(forca=2,  destreza=0, intelecto=-1,coracao=1, sombra=1, pv=12,pv_max=12),
}

# ================================================================
# PROMPTS PT-BR
# ================================================================
PROMPT_KAEL = """Você é Kael, Ladino Sombrio jogando RPG de mesa. SEMPRE em português BR.

QUEM: Ex-ladrão de Velmara. Paranóico, leal ao líder. Não confia em ninguém de fora.
DEFEITO: Vê ameaças em tudo.
VOZ: Frases curtas. Humor sombrio. Moeda no bolso. Apelidos.

RESPONDA BREVE (máx 4 linhas):
**Ação:** [1-2 frases]
**Fala:** "[1 frase]"

- Às vezes comente como jogador: *(mano, isso tá estranho)*
- Pra ações arriscadas: "Quero tentar X — rolo Destreza?"
- Pergunte ao Mestre quando fizer sentido
- Interaja com Sera e Thorne
- NÃO narre o mundo
"""

PROMPT_SERA = """Você é Sera, Clériga de Batalha jogando RPG de mesa. SEMPRE em português BR.

QUEM: Do monastério de Aelora. Acredita na redenção de todos. Ingênua.
DEFEITO: Já curou inimigos que atacaram o grupo.
VOZ: Calorosa. Fala rápido com medo. Pede desculpa demais. Metáforas da natureza.

RESPONDA BREVE (máx 4 linhas):
**Ação:** [1-2 frases]
**Fala:** "[1-2 frases]"

- Às vezes: *(ai gente, que medo)* como jogadora
- Pra ações arriscadas peça dados
- Pergunte ao Mestre: "Mestre, estou perto?" / "Mestre, consigo ver?"
- Interaja com o grupo
- NÃO narre o mundo
"""

PROMPT_THORNE = """Você é Thorne, Cavaleiro Desgraçado jogando RPG de mesa. SEMPRE em português BR.

QUEM: Ex-cavaleiro do Alvorecer Prateado. Único sobrevivente de uma missão.
DEFEITO: Se joga no perigo como se buscasse a morte.
VOZ: Formal. Autodepreciativo. Calmo em combate. Péssimo em conversa fiada.

RESPONDA BREVE (máx 4 linhas):
**Ação:** [1-2 frases]
**Fala:** "[1-2 frases]"

- Às vezes: *(essa luta vai ser feia)* como jogador
- Peça dados pra ações arriscadas
- Pergunte ao Mestre: "Mestre, quantos inimigos?"
- Se posicione entre o grupo e o perigo
- NÃO narre o mundo
"""

PROMPT_MESTRE = """Você é o Mestre de RPG de mesa. SEMPRE em português do Brasil.

REGRAS:
1. DESCREVA O MUNDO: ambiente, sons, cheiros, luz, posições de todos.
2. RESPEITE DADOS: Forte=sucesso+bônus. Parcial=sucesso+custo. Falha=consequência.
3. RITMO: Alterne tensão, respiro, descoberta. NÃO só ação.
4. Se ação exigir teste, PEÇA: "Role [Atributo]." NÃO resolva sozinho.
5. Termine com gancho ou **O que vocês fazem?**
6. Máx 4-5 parágrafos.

TOM: Fantasia sombria com calor humano.
GRUPO: Kael (ladino paranóico), Sera (clériga ingênua), Thorne (cavaleiro culpado).

CONTEXTO:
{context}
"""

PROMPT_MESTRE_RESPONDE_PCS = """Você é o Mestre de RPG de mesa. SEMPRE em português BR.

Os companheiros do grupo fizeram perguntas e observações. Responda BREVEMENTE e NATURALMENTE,
como um mestre de RPG responderia na mesa — direto, integrado à narrativa, sem repetir a cena toda.

Responda CADA pergunta dos PCs em 1-2 frases cada. Seja específico. Se a resposta revela algo
sobre o mundo, descreva. Se a pergunta não tem resposta óbvia, diga o que o personagem percebe.

NÃO repita a narração anterior. Apenas responda as perguntas.

CONTEXTO:
{context}
"""

AVENTURAS = [
    {"titulo":"A Vila Silenciosa",
     "gancho":"O grupo chega a uma vila onde ninguém fala — estão apavorados. Algo na floresta observa, e som atrai a criatura.",
     "tom":"Terror/mistério"},
    {"titulo":"A Ponte Quebrada",
     "gancho":"Caravana parada numa ponte desabada. Do outro lado, fumaça de uma fazenda. Uma criança diz que a família está lá.",
     "tom":"Dilema moral"},
    {"titulo":"O Pedido da Herdeira",
     "gancho":"Jovem nobre precisa de guarda-costas por uma noite. Alguém quer matá-la antes da herança ao amanhecer. Esconde algo.",
     "tom":"Intriga/ação"},
]

# ================================================================
# MEMÓRIA
# ================================================================
class Memoria:
    def __init__(self):
        self.eventos=[]; self.turno=0; self.fatos=[]; self.npcs={}
        self.local="Desconhecido"; self.ti=0; self.to=0; self.ch=0

    def add(self, ator, tipo, conteudo, dado=""):
        self.turno += 1
        self.eventos.append({"turno":self.turno,"ator":ator,"tipo":tipo,
                             "conteudo":conteudo,"dado":dado,"hora":datetime.now().isoformat()})

    def track(self, i, o): self.ti+=i; self.to+=o; self.ch+=1

    def contexto(self, n=15):
        p = []
        if self.fatos: p.append("## Fatos\n"+"\n".join(f"- {f}" for f in self.fatos[-10:]))
        p.append(f"\n## Estado\n- Local: {self.local}")
        for nm,st in self.npcs.items(): p.append(f"- NPC {nm}: {st}")
        ic = {"jogador":"🎮","mestre":"📖","kael":"🗡️","sera":"✨","thorne":"🛡️","sistema":"⚙️"}
        for e in self.eventos[-n:]:
            p.append(f"[T{e['turno']}] {ic.get(e['ator'],'❓')} {e['ator']}: {e['conteudo'][:250]}")
        return "\n".join(p)

    def custo(self):
        # Haiku: $0.80/M in, $4/M out | Sonnet: $3/M in, $15/M out
        # Estimativa mista (assume ~60% Haiku, ~40% Sonnet por chamada)
        ci = (self.ti/1e6)*1.68  # média ponderada
        co = (self.to/1e6)*8.40
        t = ci+co
        return {"ch":self.ch,"ti":self.ti,"to":self.to,
                "usd":round(t,4),"turno":round(t/max(self.turno,1),4)}

    def salvar(self, path):
        with open(path,"w",encoding="utf-8") as f:
            json.dump({"eventos":self.eventos,"fatos":self.fatos,"custo":self.custo()},
                      f,indent=2,ensure_ascii=False)

    def salvar_estado(self, path, nome, desc):
        with open(path,"w",encoding="utf-8") as f:
            json.dump({"v":"0.3","nome":nome,"desc":desc,"turno":self.turno,
                        "eventos":self.eventos,"fatos":self.fatos,"npcs":self.npcs,
                        "local":self.local,"ti":self.ti,"to":self.to,"ch":self.ch},
                      f,indent=2,ensure_ascii=False)

    @classmethod
    def carregar(cls, path):
        with open(path,"r",encoding="utf-8") as f: d=json.load(f)
        m=cls(); m.eventos=d.get("eventos",[]); m.turno=d.get("turno",0)
        m.fatos=d.get("fatos",[]); m.npcs=d.get("npcs",{})
        m.local=d.get("local","?"); m.ti=d.get("ti",0); m.to=d.get("to",0); m.ch=d.get("ch",0)
        return m, d.get("nome","Aventureiro"), d.get("desc","")


# ================================================================
# UTILIDADES
# ================================================================
def detectar_stat(texto):
    t = texto.lower()
    if any(w in t for w in ["força","forca","atacar","golpear","defender","bloquear"]): return Stat.FORCA
    if any(w in t for w in ["destreza","furtiv","esconder","esquivar","arco","flecha"]): return Stat.DESTREZA
    if any(w in t for w in ["intelecto","investigar","examinar","magia","procurar"]): return Stat.INTELECTO
    if any(w in t for w in ["coração","coracao","persuadir","convencer","curar","perguntar"]): return Stat.CORACAO
    if any(w in t for w in ["sombra","enganar","mentir","blefar","intimidar"]): return Stat.SOMBRA
    return Stat.INTELECTO

def detectar_tipo(texto):
    t = texto.lower()
    for kws, tp in [
        (["atacar","golpear","lutar"],"atacar"),(["defender","bloquear"],"defender"),
        (["furtiv","esconder"],"furtividade"),(["investigar","procurar","examinar"],"investigar"),
        (["persuadir","convencer","perguntar"],"persuadir"),(["enganar","mentir"],"enganar"),
        (["magia","feitiço"],"magia")]:
        if any(k in t for k in kws): return tp
    return "investigar"

def pc_quer_rolar(texto):
    tl = texto.lower()
    return any(x in tl for x in ["rolo ","rolar ","quero tentar","posso rolar",
                                   "faço um teste","rolo destreza","rolo força",
                                   "rolo intelecto","rolo coração","rolo sombra"])

def pc_fez_pergunta(texto):
    """Detecta se o PC fez pergunta ao Mestre."""
    tl = texto.lower()
    return any(x in tl for x in ["mestre,","mestre ","consigo ver","consigo sentir",
                                   "consigo ouvir","há algum","tem algum","quantos",
                                   "estou perto","posso alcançar","é possível"])
