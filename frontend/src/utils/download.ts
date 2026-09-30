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

/** Abre cada documento selecionado numa aba (blob autenticado). */
export async function abrirEmAbas(docs: DocComRegistro[]): Promise<void> {
  for (const d of docs) {
    try {
      const blob = await buscarImagemBlob(d.id, "full");
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch {
      /* documento sem imagem: ignora */
    }
  }
}
