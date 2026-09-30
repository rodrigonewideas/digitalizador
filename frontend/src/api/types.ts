export interface Usuario {
  id: number;
  login: string;
  nome: string | null;
  email: string;
  status: string;
  is_admin: boolean;
  grupo_id: number;
  email_verificado: boolean;
  data_cadastro?: string | null;
}

export interface Cessionario {
  contrato: number | null;
  nr_contrato: string | null;
  nr_terreno: string | null;
  nome_cessionario: string | null;
  cessionarios: string[] | null;
  cpf: string | null;
  tipo_terreno: string | null;
  falecido: string | null;
  dt_venda: string | null;
  vendedor: string | null;
}

export interface RegistroBusca {
  id: number;
  contrato: number | null;
  lote: string | null;
  titular: number | null;
  sepultado: number | null;
  qtde_documentos: number;
  qtde_refugados: number;
  cessionario: Cessionario | null;
}

export interface Documento {
  id: number;
  tipo_doc_id: number | null;
  tipo_descricao: string | null;
  nr_folha: number | null;
  total_folhas: number | null;
  face: string | null;
  refugada: boolean;
  qtde_assinaturas: number;
  qtde_comentarios: number;
}

export interface TipoDocumento {
  id: number;
  descricao: string;
  descricao_detalhada: string | null;
  frente_verso: boolean;
  qtde_folhas: number;
  pagina_inicial: number | null;
  ativo: boolean;
}

export interface Motivo {
  id: number;
  descricao: string;
}

export interface Certificado {
  id: number;
  nome_titular: string | null;
  cpf_cnpj: string | null;
  numero_serie: string | null;
  emissor: string | null;
  validade_inicio: string | null;
  validade_fim: string | null;
  ativo: boolean;
}

export interface AssinaturaItem {
  ordem: number;
  usuario_id: number;
  assinado_em: string;
  titular: string | null;
  carimbo_nova_folha: boolean;
  carimbo_pagina: number | null;
  status: string;
  hash_documento: string | null;
}

export interface AssinaturasResumo {
  documento_id: number;
  qtde_assinaturas: number;
  assinaturas_no_pdf: number | null;
  assinaturas: AssinaturaItem[];
}
