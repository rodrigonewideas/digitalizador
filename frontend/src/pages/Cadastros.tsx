import { CrudPage } from "../components/CrudPage";

const filtroNome = { campo: "descricao", label: "Nome", tipo: "texto" as const };
const filtroSituacao = { campo: "ativo", label: "Situação", tipo: "ativo" as const };
const filtroCadastro = { campo: "created_at", label: "Cadastro", tipo: "data" as const };

export function MotivosPage() {
  return (
    <CrudPage
      titulo="Motivos"
      singular="Motivo"
      descricao="Motivos de refugo/comentário de documentos."
      endpoint="/motivos"
      colunas={[
        { key: "id", label: "Código", tipo: "num" },
        { key: "descricao", label: "Descrição" },
      ]}
      campos={[{ key: "descricao", label: "Descrição", tipo: "text", obrigatorio: true, full: true }]}
      filtros={[filtroNome]}
    />
  );
}

export function IndicesOriginalPage() {
  return (
    <CrudPage
      titulo="Índice Original"
      singular="Índice"
      descricao="Índices de arquivamento originais."
      endpoint="/indices-original"
      colunas={[
        { key: "id", label: "Código", tipo: "num" },
        { key: "descricao", label: "Descrição" },
      ]}
      campos={[{ key: "descricao", label: "Descrição", tipo: "text", obrigatorio: true, full: true }]}
      filtros={[filtroNome]}
    />
  );
}

export function IndicesAposPage() {
  return (
    <CrudPage
      titulo="Índice Após 1999"
      singular="Índice"
      descricao="Índices de arquivamento pós-1999."
      endpoint="/indices-apos-1999"
      colunas={[
        { key: "id", label: "Código", tipo: "num" },
        { key: "descricao", label: "Descrição" },
      ]}
      campos={[{ key: "descricao", label: "Descrição", tipo: "text", obrigatorio: true, full: true }]}
      filtros={[filtroNome]}
    />
  );
}

export function GruposPage() {
  return (
    <CrudPage
      titulo="Setores"
      singular="Setor"
      descricao="Setores (grupos) para controle de acesso."
      endpoint="/grupos"
      colunas={[
        { key: "id", label: "Código", tipo: "num" },
        { key: "descricao", label: "Descrição" },
        { key: "ativo", label: "Situação", tipo: "ativo" },
        { key: "created_at", label: "Cadastro", tipo: "data" },
      ]}
      campos={[
        { key: "descricao", label: "Descrição", tipo: "text", obrigatorio: true },
        { key: "ativo", label: "Ativo", tipo: "checkbox", padrao: true },
      ]}
      filtros={[filtroNome, filtroSituacao, filtroCadastro]}
    />
  );
}

export function CaracteristicasPage() {
  return (
    <CrudPage
      titulo="Características"
      singular="Característica"
      endpoint="/caracteristicas"
      colunas={[
        { key: "id", label: "Código", tipo: "num" },
        { key: "nome", label: "Nome" },
        { key: "ativo", label: "Situação", tipo: "ativo" },
      ]}
      campos={[
        { key: "nome", label: "Nome", tipo: "text", obrigatorio: true },
        { key: "ativo", label: "Ativo", tipo: "checkbox", padrao: true },
      ]}
      filtros={[
        { campo: "nome", label: "Nome", tipo: "texto" },
        filtroSituacao,
      ]}
    />
  );
}

export function TiposDocumentoPage() {
  return (
    <CrudPage
      titulo="Tipos de Documento"
      singular="Tipo de Documento"
      descricao="Catálogo de tipos de documento da digitalização."
      endpoint="/tipos-documento"
      colunas={[
        { key: "descricao", label: "Descrição" },
        { key: "descricao_detalhada", label: "Detalhe" },
        { key: "frente_verso", label: "Frente/Verso", tipo: "bool" },
        { key: "qtde_folhas", label: "Folhas", tipo: "num" },
        { key: "ativo", label: "Situação", tipo: "ativo" },
        { key: "created_at", label: "Cadastro", tipo: "data" },
      ]}
      campos={[
        { key: "descricao", label: "Descrição", tipo: "text", obrigatorio: true },
        { key: "descricao_detalhada", label: "Descrição detalhada", tipo: "text", full: true },
        { key: "indicacao_frente", label: "Dica da frente", tipo: "text", full: true },
        { key: "qtde_folhas", label: "Qtde de folhas", tipo: "number", padrao: 1 },
        { key: "pagina_inicial", label: "Página inicial", tipo: "number" },
        { key: "frente_verso", label: "Frente/Verso", tipo: "checkbox", padrao: false },
        { key: "ativo", label: "Ativo", tipo: "checkbox", padrao: true },
      ]}
      filtros={[filtroNome, filtroSituacao, filtroCadastro]}
    />
  );
}
