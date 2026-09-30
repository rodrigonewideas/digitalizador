import JSZip from "jszip";

import { api } from "../api/client";
import type { Documento, RegistroBusca } from "../api/types";

export interface DocComRegistro extends Documento {
  registro: RegistroBusca;
}

export function buscarImagemBlob(docId: number, versao: "full" | "thumb" = "full"): Promise<Blob> {
  return api<Blob>(`/documentos/${docId}/imagem?versao=${versao}`);
}

export function salvarBlob(nome: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nome;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function limpar(s: string): string {
  return s.replace(/[\\/:*?"<>|]+/g, "-").replace(/\s+/g, " ").trim();
}

export function nomeArquivoDoc(d: DocComRegistro): string {
  const contrato = d.registro.cessionario?.nr_contrato ?? String(d.registro.contrato ?? d.registro.id);
  const tipo = d.tipo_descricao ?? "Documento";
  const folha = d.nr_folha != null ? `_f${d.nr_folha}` : "";
  const face = d.face ? d.face : "";
  return limpar(`${contrato}_${tipo}${folha}${face}_${d.id}.jpg`);
}

/** Baixa os documentos selecionados como um único ZIP (imagens full). */
export async function baixarComoZip(
  docs: DocComRegistro[],
  onProgresso?: (feitos: number, total: number) => void,
): Promise<{ ok: number; falhas: number }> {
  const zip = new JSZip();
  let ok = 0;
  let falhas = 0;
  for (const [i, d] of docs.entries()) {
    try {
      const blob = await buscarImagemBlob(d.id, "full");
      zip.file(nomeArquivoDoc(d), blob);
      ok += 1;
    } catch {
      falhas += 1;
    }
    onProgresso?.(i + 1, docs.length);
  }
  if (ok > 0) {
    const conteudo = await zip.generateAsync({ type: "blob" });
    const hoje = new Date().toISOString().slice(0, 10);
    salvarBlob(`documentos_bonfim_${hoje}.zip`, conteudo);
  }
  return { ok, falhas };
}

/**
 * Abre UMA guia com todos os documentos selecionados em sequência (pronta para
 * imprimir com Ctrl+P). Uma única janela evita o bloqueador de pop-ups; a guia
 * deve ser aberta de forma síncrona (dentro do clique), por isso primeiro
 * abre-se o esqueleto e as imagens chegam em seguida.
 */
export async function abrirSelecionadosEmGuia(docs: DocComRegistro[]): Promise<boolean> {
  const w = window.open("", "_blank");
  if (!w) return false; // pop-up bloqueado
  const dw = w.document;
  dw.title = "Documentos selecionados — Digitalizador Bonfim";
  dw.head.innerHTML = `<meta charset="utf-8"><style>
    body{margin:0;background:#1c211d;font:14px system-ui;padding:16px}
    h1{font-size:15px;font-weight:600;margin:0 0 14px;color:#e8ede9}
    .doc{background:#fff;color:#222;border-radius:8px;margin:0 auto 18px;max-width:980px;padding:10px}
    .doc header{font-size:12px;color:#444;padding:2px 4px 8px}
    .doc img{width:100%;display:block;border-radius:4px}
    .falta{padding:30px;text-align:center;color:#888}
    @media print{body{background:#fff;padding:0}h1{display:none}
      .doc{page-break-after:always;max-width:none;margin:0;border-radius:0;padding:0}
      .doc header{padding:4px 0}}
  </style>`;
  dw.body.innerHTML = "";
  const titulo = dw.createElement("h1");
  titulo.textContent = `Documentos selecionados (0/${docs.length})…`;
  dw.body.appendChild(titulo);

  let feitos = 0;
  for (const d of docs) {
    const sec = dw.createElement("section");
    sec.className = "doc";
    const cab = dw.createElement("header");
    const contrato = d.registro.cessionario?.nr_contrato ?? String(d.registro.contrato ?? "—");
    const nome = d.registro.cessionario?.nome_cessionario ?? "";
    cab.textContent =
      `${d.tipo_descricao ?? "Documento"} · nº ${d.id} · contrato ${contrato}` +
      (nome ? ` · ${nome}` : "") +
      ` · pg ${d.nr_folha ?? "?"}${d.total_folhas ? `/${d.total_folhas}` : ""}` +
      (d.face ? (d.face === "F" ? " · frente" : " · verso") : "");
    sec.appendChild(cab);
    try {
      const blob = await buscarImagemBlob(d.id, "full");
      const img = dw.createElement("img");
      img.src = URL.createObjectURL(blob);
      sec.appendChild(img);
    } catch {
      const p = dw.createElement("p");
      p.className = "falta";
      p.textContent = "Imagem ainda não disponível no storage.";
      sec.appendChild(p);
    }
    dw.body.appendChild(sec);
    feitos += 1;
    titulo.textContent = `Documentos selecionados (${feitos}/${docs.length})…`;
  }
  titulo.textContent = `Documentos selecionados (${docs.length}) — Ctrl+P para imprimir`;
  return true;
}
