// FINANÇA - JavaScript Principal

// ============================================================================
// TOOLTIP GLOBAL (GLASSMORPHISM)
// ============================================================================

let tooltipElement = null;

function initTooltipGlobal() {
    // Criar elemento do tooltip se não existir
    if (!tooltipElement) {
        tooltipElement = document.createElement('div');
        tooltipElement.className = 'tooltip-glass';
        document.body.appendChild(tooltipElement);
    }

    // Usar event delegation para capturar todos os badges
    document.addEventListener('mouseenter', function(e) {
        const badge = e.target.closest('[data-tooltip]');
        if (badge) {
            showTooltip(badge);
        }
    }, true);

    document.addEventListener('mouseleave', function(e) {
        const badge = e.target.closest('[data-tooltip]');
        if (badge) {
            hideTooltip();
        }
    }, true);
}

function showTooltip(element) {
    const text = element.getAttribute('data-tooltip');
    if (!text || !tooltipElement) return;

    tooltipElement.textContent = text;
    tooltipElement.classList.add('visible');

    // Posicionar o tooltip
    const rect = element.getBoundingClientRect();
    const tooltipRect = tooltipElement.getBoundingClientRect();

    let left = rect.left + (rect.width / 2) - (tooltipRect.width / 2);
    let top = rect.top - tooltipRect.height - 10;

    // Ajustar se sair da tela
    if (left < 10) left = 10;
    if (left + tooltipRect.width > window.innerWidth - 10) {
        left = window.innerWidth - tooltipRect.width - 10;
    }
    if (top < 10) {
        // Mostrar abaixo se não couber acima
        top = rect.bottom + 10;
        tooltipElement.style.setProperty('--arrow-position', 'top');
    }

    tooltipElement.style.left = left + 'px';
    tooltipElement.style.top = top + 'px';
}

function hideTooltip() {
    if (tooltipElement) {
        tooltipElement.classList.remove('visible');
    }
}

// Auto-fechar alertas após 5 segundos
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });

    // Inicializar tabelas expansíveis
    initExpandableTable();

    // Inicializar tooltip global
    initTooltipGlobal();
});

// Formatar valores como moeda
function formatarMoeda(valor) {
    return new Intl.NumberFormat('pt-BR', {
        style: 'currency',
        currency: 'BRL'
    }).format(valor);
}

// Formatar data
function formatarData(dataStr) {
    if (!dataStr || dataStr === '--') return '--';

    // Se já está formatada (DD/MM/YYYY), retorna direto
    if (/^\d{2}\/\d{2}\/\d{4}$/.test(dataStr)) {
        return dataStr;
    }

    // Tentar parsear formato ISO (YYYY-MM-DD)
    if (/^\d{4}-\d{2}-\d{2}/.test(dataStr)) {
        const partes = dataStr.split('-');
        return `${partes[2].substring(0,2)}/${partes[1]}/${partes[0]}`;
    }

    // Fallback
    try {
        const data = new Date(dataStr);
        if (!isNaN(data.getTime())) {
            return data.toLocaleDateString('pt-BR');
        }
    } catch (e) {}

    return dataStr;
}

// ============================================================================
// TABELAS EXPANSÍVEIS
// ============================================================================

function initExpandableTable() {
    const categoryRows = document.querySelectorAll('.category-row');

    categoryRows.forEach(row => {
        row.addEventListener('click', function() {
            toggleCategory(this);
        });
    });
}

async function toggleCategory(row) {
    const detailRow = row.nextElementSibling;
    const isExpanded = row.classList.contains('expanded');

    if (isExpanded) {
        // Fechar categoria
        row.classList.remove('expanded');
        detailRow.classList.add('hidden');

        // Fechar todas as subcategorias dentro desta categoria
        const subcategorias = detailRow.querySelectorAll('.subcategoria-group.expanded');
        subcategorias.forEach(group => {
            group.classList.remove('expanded');
            const content = group.querySelector('.subcategoria-content');
            const icon = group.querySelector('.expand-icon');
            if (content) content.classList.add('hidden');
            if (icon) icon.textContent = '▶';
        });
    } else {
        // Abrir
        row.classList.add('expanded');
        detailRow.classList.remove('hidden');

        // Carregar dados se ainda não carregou
        const container = detailRow.querySelector('.detail-container');
        if (container.querySelector('.detail-loading')) {
            await loadTransactions(row, container);
        }
    }
}

// Cache de categorias
let categoriasCache = null;

async function loadTransactions(row, container) {
    const categoria = row.dataset.categoria;
    const mes = row.dataset.mes;

    try {
        // Buscar transações primeiro (obrigatório)
        const transacoesRes = await fetch(`/api/transacoes/${mes}?categoria=${encodeURIComponent(categoria)}`);
        const transacoes = await transacoesRes.json();

        // Buscar variações (opcional - não bloqueia se falhar)
        let variacoes = {};
        try {
            const variacoesRes = await fetch(`/api/variacao-subcategorias/${mes}?categoria=${encodeURIComponent(categoria)}`);
            if (variacoesRes.ok) {
                variacoes = await variacoesRes.json();
            }
        } catch (e) {
            console.warn('Não foi possível carregar variações:', e);
        }

        if (transacoes.length === 0) {
            container.innerHTML = '<p class="text-muted">Nenhuma transação encontrada</p>';
            return;
        }

        // Agrupar transações por subcategoria
        const porSubcategoria = {};
        transacoes.forEach(tx => {
            const subcat = tx.subcategoria || 'Sem subcategoria';
            if (!porSubcategoria[subcat]) {
                porSubcategoria[subcat] = { transacoes: [], total: 0 };
            }
            porSubcategoria[subcat].transacoes.push(tx);
            porSubcategoria[subcat].total += tx.valor;
        });

        // Ordenar subcategorias por total (maior primeiro)
        const subcategorias = Object.keys(porSubcategoria).sort((a, b) =>
            porSubcategoria[b].total - porSubcategoria[a].total
        );

        let html = '';

        // VERIFICAÇÃO INTELIGENTE:
        // Se houver apenas uma "subcategoria" e ela for vazia/nula/"Sem subcategoria",
        // mostramos a lista plana (flat) diretamente, sem criar o acordeão.
        const isSingleUncategorized = subcategorias.length === 1 && 
                                     (subcategorias[0] === 'Sem subcategoria' || 
                                      subcategorias[0] === '' || 
                                      subcategorias[0] === 'null');

        if (isSingleUncategorized) {
            // MODO PLANO (FLAT VIEW)
            const grupo = porSubcategoria[subcategorias[0]];
            html += `
                <div class="transactions-flat-container" style="padding: 10px 15px;">
                    <table class="transactions-table sortable">
                        <thead>
                            <tr>
                                <th style="width: 24px; min-width: 24px; max-width: 24px; padding: 0;"></th>
                                <th data-sort="string" style="cursor: pointer;">Descrição <span class="sort-icon">↕</span></th>
                                <th data-sort="string" style="cursor: pointer;">Subcategoria <span class="sort-icon">↕</span></th>
                                <th data-sort="string" style="cursor: pointer;">Parcela <span class="sort-icon">↕</span></th>
                                <th data-sort="number" style="text-align: right; cursor: pointer;">Valor <span class="sort-icon">↕</span></th>
                            </tr>
                        </thead>
                        <tbody>
            `;
            
            grupo.transacoes.forEach(tx => {
                html += renderTransactionRow(tx, categoria);
            });

            html += `
                        </tbody>
                    </table>
                </div>
            `;
        } else {
            // MODO HIERÁRQUICO (PADRÃO)
            html += '<div class="subcategorias-container">';

            subcategorias.forEach(subcat => {
                const grupo = porSubcategoria[subcat];
                const variacaoData = variacoes[subcat] || {};
                const variacaoPct = variacaoData.variacao_pct || 0;

                // Gerar badge de variação para subcategoria
                let variacaoBadge = '';
                // Sempre mostrar badge se houver dados históricos (mesmo que seja 0%)
                if (variacaoData.media_historica !== undefined) {
                    let classe, icon, tooltip;
                    
                    if (variacaoPct === 0) {
                        classe = 'text-neutral';
                        icon = '~';
                        tooltip = 'Gasto estável vs mês anterior';
                    } else {
                        const isAumento = variacaoPct > 0;
                        classe = isAumento ? 'text-danger' : 'text-success';
                        icon = isAumento ? '▲' : '▼';
                        tooltip = isAumento
                            ? `Aumento de ${formatarMoeda(Math.abs(variacaoData.total_atual - variacaoData.media_historica))} vs mês anterior`
                            : `Redução de ${formatarMoeda(Math.abs(variacaoData.total_atual - variacaoData.media_historica))} vs mês anterior`;
                    }
                    
                    variacaoBadge = `<span class="variation-badge ${classe}" data-tooltip="${tooltip}">${icon} ${Math.abs(variacaoPct).toFixed(0)}%</span>`;
                }

                html += `
                    <div class="subcategoria-group">
                        <div class="subcategoria-header" data-categoria="${categoria}" data-subcategoria="${subcat}" onclick="toggleSubcategoria(this)">
                            <span class="expand-icon">▶</span>
                            <span class="subcategoria-nome">${subcat}${variacaoBadge}</span>
                            <span class="subcategoria-stats">
                                <span class="subcategoria-qtd">${grupo.transacoes.length} item${grupo.transacoes.length !== 1 ? 's' : ''}</span>
                                <span class="subcategoria-total">${formatarMoeda(grupo.total)}</span>
                            </span>
                        </div>
                        <div class="subcategoria-content hidden">
                            <table class="transactions-table sortable">
                                <thead>
                                    <tr>
                                        <th style="width: 24px; min-width: 24px; max-width: 24px; padding: 0;"></th>
                                        <th data-sort="string" style="cursor: pointer;">Descrição <span class="sort-icon">↕</span></th>
                                        <th data-sort="string" style="cursor: pointer;">Subcategoria <span class="sort-icon">↕</span></th>
                                        <th data-sort="string" style="cursor: pointer;">Parcela <span class="sort-icon">↕</span></th>
                                        <th data-sort="number" style="text-align: right; cursor: pointer;">Valor <span class="sort-icon">↕</span></th>
                                    </tr>
                                </thead>
                                <tbody>
                `;

                grupo.transacoes.forEach(tx => {
                    html += renderTransactionRow(tx, categoria);
                });

                html += `
                                </tbody>
                            </table>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
        }

        container.innerHTML = html;

        // Inicializar ordenação em todas as tabelas
        container.querySelectorAll('table.sortable').forEach(table => {
            initTableSorting(table);
        });

        // Inicializar edição de categorias e subcategorias
        initCategoryEdit(container);
        initSubcategoryEdit(container);

        // Inicializar edição de descrições
        initDescriptionEdit(container);

        // Inicializar drag para recorrentes
        initTransactionDrag(container);

    } catch (error) {
        console.error('Erro ao carregar transações:', error);
        container.innerHTML = '<p class="text-muted">Erro ao carregar dados</p>';
    }
}

// Renderiza uma linha de transação (sem badges de variação - agora são exibidos na subcategoria)
function renderTransactionRow(tx, categoria) {
    const valorClass = tx.valor < 0 ? 'negative' : 'positive';
    const txId = tx.id || '';
    const descricaoEscaped = (tx.descricao || '').replace(/"/g, '&quot;');
    const descricaoOriginalEscaped = (tx.descricao_original || tx.descricao || '').replace(/"/g, '&quot;');

    // Indicador de mapeamento
    let mapeamentoHtml = '';
    if (tx.tem_mapeamento) {
        mapeamentoHtml = `<span class="badge-mapeamento" data-tooltip="Original: ${descricaoOriginalEscaped}">✦</span>`;
    }

    return `
        <tr data-tx-id="${txId}"
            data-descricao="${descricaoEscaped}"
            data-descricao-original="${descricaoOriginalEscaped}"
            data-tem-mapeamento="${tx.tem_mapeamento || false}"
            data-categoria="${(tx.categoria || '').replace(/"/g, '&quot;')}"
            data-subcategoria="${(tx.subcategoria || '').replace(/"/g, '&quot;')}"
            data-valor="${tx.valor}"
            draggable="true"
            class="tx-draggable">
            <td class="drag-handle-tx" title="Arraste para adicionar como recorrente">⠿</td>
            <td class="tx-desc editable-desc" title="Clique para editar descrição">${tx.descricao}${mapeamentoHtml}<span class="edit-icon desc-edit-icon" title="Editar descrição">✎</span></td>
            <td class="tx-subcat ${txId ? 'editable' : ''}" data-categoria="${tx.categoria || ''}" data-subcategoria="${tx.subcategoria || ''}">${tx.subcategoria || '<span class="text-muted">-</span>'} ${txId ? '<span class="edit-icon" title="Editar subcategoria">✎</span>' : ''}</td>
            <td class="tx-parcela">${tx.parcela || 'Única'}</td>
            <td class="tx-value ${valorClass}" data-val="${tx.valor}">${formatarMoeda(tx.valor)}</td>
        </tr>
    `;
}

// Toggle subcategoria
function toggleSubcategoria(header) {
    const group = header.closest('.subcategoria-group');
    const content = group.querySelector('.subcategoria-content');
    const icon = header.querySelector('.expand-icon');

    const isExpanded = !content.classList.contains('hidden');

    if (isExpanded) {
        content.classList.add('hidden');
        icon.textContent = '▶';
        group.classList.remove('expanded');
    } else {
        content.classList.remove('hidden');
        icon.textContent = '▼';
        group.classList.add('expanded');
    }
}

// ============================================================================
// EDIÇÃO DE CATEGORIAS
// ============================================================================

async function getCategorias() {
    if (categoriasCache) return categoriasCache;

    try {
        const response = await fetch('/api/categorias');
        categoriasCache = await response.json();
        return categoriasCache;
    } catch (error) {
        console.error('Erro ao carregar categorias:', error);
        return {};
    }
}

function initCategoryEdit(container) {
    const editableCells = container.querySelectorAll('.tx-cat.editable');

    editableCells.forEach(cell => {
        cell.addEventListener('click', async function(e) {
            e.stopPropagation();

            // Evitar múltiplos dropdowns
            if (cell.querySelector('.category-dropdown')) return;

            const row = cell.closest('tr');
            const txId = row.dataset.txId;
            if (!txId) return;

            const categoriaAtual = cell.dataset.categoria;
            const categorias = await getCategorias();

            // Criar dropdown
            // Criar dropdown (adiciona ao body para evitar overflow)
            const dropdown = document.createElement('div');
            dropdown.className = 'category-dropdown category-dropdown-fixed';

            let optionsHtml = '<div class="dropdown-header">';
            optionsHtml += '<input type="text" placeholder="Buscar categoria..." class="dropdown-search-input">';
            optionsHtml += '</div>';
            optionsHtml += '<div class="dropdown-options">';

            Object.keys(categorias).forEach(cat => {
                const isSelected = cat === categoriaAtual ? 'selected' : '';
                optionsHtml += `<div class="dropdown-option ${isSelected}" data-categoria="${cat}">${cat}</div>`;
            });

            optionsHtml += '</div>';

            dropdown.innerHTML = optionsHtml;
            document.body.appendChild(dropdown);

            // Posicionar dropdown próximo à célula
            const rect = cell.getBoundingClientRect();
            dropdown.style.top = `${rect.bottom + 4}px`;
            dropdown.style.left = `${rect.left}px`;

            // Focar na busca
            const searchInput = dropdown.querySelector('.dropdown-search-input');
            searchInput.focus();

            // Filtrar opções
            searchInput.addEventListener('input', function() {
                const filter = this.value.toLowerCase();
                const options = dropdown.querySelectorAll('.dropdown-option');
                options.forEach(opt => {
                    const text = opt.textContent.toLowerCase();
                    opt.style.display = text.includes(filter) ? '' : 'none';
                });
            });

            // Selecionar opção
            dropdown.querySelectorAll('.dropdown-option').forEach(option => {
                option.addEventListener('click', async function(e) {
                    e.stopPropagation();
                    const novaCategoria = this.dataset.categoria;

                    await atualizarCategoria(txId, novaCategoria, null, cell);
                    dropdown.remove();
                });
            });

            // Fechar ao clicar fora
            document.addEventListener('click', function closeDropdown(e) {
                if (!dropdown.contains(e.target) && e.target !== cell) {
                    dropdown.remove();
                    document.removeEventListener('click', closeDropdown);
                }
            });
        });
    });
}

async function atualizarCategoria(txId, categoria, subcategoria, cell) {
    try {
        const row = cell.closest('tr');
        const descricao = row?.dataset.descricao;
        const categoriaAnterior = row?.dataset.categoria;

        const response = await fetch(`/api/transacoes/${txId}/categoria`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                categoria: categoria,
                subcategoria: subcategoria
            })
        });

        const result = await response.json();

        if (result.success) {
            const qtd = result.transacoes_atualizadas || 1;
            showToast(`Categoria atualizada em ${qtd} transação${qtd > 1 ? 's' : ''} similar${qtd > 1 ? 'es' : ''}`);

            // Se mudou a categoria, remover visualmente (foi para outro grupo)
            if (categoriaAnterior !== categoria && descricao) {
                removerTransacoesVisuais(descricao);
            } else {
                // Apenas atualizar a célula
                cell.dataset.categoria = categoria;
                cell.innerHTML = `${categoria} <span class="edit-icon" title="Editar categoria">✎</span>`;
                cell.classList.add('editable');
                initCategoryEdit(cell.closest('.detail-container') || cell.closest('.recorrentes-group-content'));
            }
        } else {
            showToast('Erro ao atualizar categoria', 'error');
        }
    } catch (error) {
        console.error('Erro:', error);
        showToast('Erro ao atualizar categoria', 'error');
    }
}

// Inicializar edição de subcategorias
function initSubcategoryEdit(container) {
    const editableCells = container.querySelectorAll('.tx-subcat.editable');

    editableCells.forEach(cell => {
        cell.addEventListener('click', async function(e) {
            e.stopPropagation();

            // Evitar múltiplos dropdowns
            if (cell.querySelector('.category-dropdown')) return;

            const row = cell.closest('tr');
            const txId = row.dataset.txId;
            if (!txId) return;

            const categoriaAtual = cell.dataset.categoria;
            const subcategoriaAtual = cell.dataset.subcategoria;
            const categorias = await getCategorias();

            // Obter subcategorias da categoria atual
            const subcategorias = categorias[categoriaAtual] || [];

            // Criar dropdown (adiciona ao body para evitar overflow)
            const dropdown = document.createElement('div');
            dropdown.className = 'category-dropdown category-dropdown-fixed';

            let optionsHtml = '<div class="dropdown-header">';
            optionsHtml += '<input type="text" placeholder="Buscar subcategoria..." class="dropdown-search-input">';
            optionsHtml += '</div>';
            optionsHtml += '<div class="dropdown-options">';

            // Opção para remover subcategoria
            optionsHtml += `<div class="dropdown-option ${!subcategoriaAtual ? 'selected' : ''}" data-subcategoria="">Sem subcategoria</div>`;

            subcategorias.forEach(subcat => {
                const isSelected = subcat === subcategoriaAtual ? 'selected' : '';
                optionsHtml += `<div class="dropdown-option ${isSelected}" data-subcategoria="${subcat}">${subcat}</div>`;
            });

            optionsHtml += '</div>';

            dropdown.innerHTML = optionsHtml;
            document.body.appendChild(dropdown);

            // Posicionar dropdown próximo à célula
            const rect = cell.getBoundingClientRect();
            dropdown.style.top = `${rect.bottom + 4}px`;
            dropdown.style.left = `${rect.left}px`;

            // Focar na busca
            const searchInput = dropdown.querySelector('.dropdown-search-input');
            searchInput.focus();

            // Filtrar opções
            searchInput.addEventListener('input', function() {
                const filter = this.value.toLowerCase();
                const options = dropdown.querySelectorAll('.dropdown-option');
                options.forEach(opt => {
                    const text = opt.textContent.toLowerCase();
                    opt.style.display = text.includes(filter) ? '' : 'none';
                });
            });

            // Selecionar opção
            dropdown.querySelectorAll('.dropdown-option').forEach(option => {
                option.addEventListener('click', async function(e) {
                    e.stopPropagation();
                    const novaSubcategoria = this.dataset.subcategoria || null;

                    await atualizarSubcategoria(txId, categoriaAtual, novaSubcategoria, cell);
                    dropdown.remove();
                });
            });

            // Fechar ao clicar fora
            document.addEventListener('click', function closeDropdown(e) {
                if (!dropdown.contains(e.target) && e.target !== cell) {
                    dropdown.remove();
                    document.removeEventListener('click', closeDropdown);
                }
            });
        });
    });
}

async function atualizarSubcategoria(txId, categoria, subcategoria, cell) {
    try {
        const row = cell.closest('tr');
        const descricao = row?.dataset.descricao;
        const subcategoriaAnterior = cell.dataset.subcategoria;

        const response = await fetch(`/api/transacoes/${txId}/categoria`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                categoria: categoria,
                subcategoria: subcategoria
            })
        });

        const result = await response.json();

        if (result.success) {
            const qtd = result.transacoes_atualizadas || 1;
            showToast(`Subcategoria atualizada em ${qtd} transação${qtd > 1 ? 's' : ''} similar${qtd > 1 ? 'es' : ''}`);

            // Se mudou a subcategoria, remover visualmente (foi para outro grupo)
            if (subcategoriaAnterior !== (subcategoria || '') && descricao) {
                removerTransacoesVisuais(descricao);
            } else {
                // Apenas atualizar a célula
                cell.dataset.subcategoria = subcategoria || '';
                cell.innerHTML = `${subcategoria || '<span class="text-muted">-</span>'} <span class="edit-icon" title="Editar subcategoria">✎</span>`;
                initSubcategoryEdit(cell.closest('.subcategoria-content'));
            }
        } else {
            showToast('Erro ao atualizar subcategoria', 'error');
        }
    } catch (error) {
        console.error('Erro:', error);
        showToast('Erro ao atualizar subcategoria', 'error');
    }
}

function showToast(message, type = 'success') {
    // Remover toast existente
    const existingToast = document.querySelector('.toast-notification');
    if (existingToast) existingToast.remove();

    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    // Animar entrada
    setTimeout(() => toast.classList.add('show'), 10);

    // Remover após 3 segundos
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ============================================================================
// EDIÇÃO DE DESCRIÇÕES (MAPEAMENTO)
// ============================================================================

function initDescriptionEdit(container) {
    const editableCells = container.querySelectorAll('.tx-desc.editable-desc');

    editableCells.forEach(cell => {
        cell.addEventListener('click', function(e) {
            e.stopPropagation();

            // Evitar múltiplas edições
            if (cell.querySelector('.desc-edit-input')) return;

            const row = cell.closest('tr');
            const descricaoAtual = row.dataset.descricao;
            const descricaoOriginal = row.dataset.descricaoOriginal || descricaoAtual;
            const temMapeamento = row.dataset.temMapeamento === 'true';

            // Guardar conteúdo original da célula
            const conteudoOriginal = cell.innerHTML;

            // Criar input de edição
            const editContainer = document.createElement('div');
            editContainer.className = 'desc-edit-container';
            editContainer.innerHTML = `
                <input type="text" class="desc-edit-input" value="${descricaoAtual.replace(/"/g, '&quot;')}" />
                <div class="desc-edit-actions">
                    <button class="btn-desc-save" title="Salvar">✓</button>
                    <button class="btn-desc-cancel" title="Cancelar">✕</button>
                    ${temMapeamento ? '<button class="btn-desc-reset" title="Restaurar original">↺</button>' : ''}
                </div>
                <div class="desc-edit-hint">Original: ${descricaoOriginal}</div>
            `;

            cell.innerHTML = '';
            cell.appendChild(editContainer);

            const input = editContainer.querySelector('.desc-edit-input');
            input.focus();
            input.select();

            // Salvar ao clicar no botão ou pressionar Enter
            const salvar = async () => {
                const novaDescricao = input.value.trim();
                if (novaDescricao && novaDescricao !== descricaoAtual) {
                    await salvarMapeamentoDescricao(descricaoOriginal, novaDescricao, row, cell);
                } else {
                    cancelar();
                }
            };

            // Cancelar edição
            const cancelar = () => {
                cell.innerHTML = conteudoOriginal;
            };

            // Restaurar descrição original (remover mapeamento)
            const restaurar = async () => {
                await deletarMapeamentoDescricao(descricaoOriginal, row, cell);
            };

            editContainer.querySelector('.btn-desc-save').addEventListener('click', (e) => {
                e.stopPropagation();
                salvar();
            });

            editContainer.querySelector('.btn-desc-cancel').addEventListener('click', (e) => {
                e.stopPropagation();
                cancelar();
            });

            const resetBtn = editContainer.querySelector('.btn-desc-reset');
            if (resetBtn) {
                resetBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    restaurar();
                });
            }

            input.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    salvar();
                } else if (e.key === 'Escape') {
                    cancelar();
                }
            });

            // Prevenir que o clique no container feche a edição
            editContainer.addEventListener('click', (e) => e.stopPropagation());
        });
    });
}

async function salvarMapeamentoDescricao(descricaoOriginal, descricaoCustomizada, row, cell) {
    try {
        const response = await fetch('/api/mapeamento-descricao', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                descricao_original: descricaoOriginal,
                descricao_customizada: descricaoCustomizada
            })
        });

        const result = await response.json();

        if (result.success) {
            // Atualizar a row com os novos dados
            row.dataset.descricao = descricaoCustomizada;
            row.dataset.descricaoOriginal = descricaoOriginal;
            row.dataset.temMapeamento = 'true';

            // Atualizar a célula
            cell.innerHTML = `${descricaoCustomizada}<span class="badge-mapeamento" data-tooltip="Original: ${descricaoOriginal}">✦</span><span class="edit-icon desc-edit-icon" title="Editar descrição">✎</span>`;

            showToast(`Descrição mapeada! Futuras importações usarão "${descricaoCustomizada}"`);
        } else {
            showToast('Erro ao salvar mapeamento', 'error');
            // Restaurar célula
            cell.innerHTML = `${row.dataset.descricao}<span class="edit-icon desc-edit-icon" title="Editar descrição">✎</span>`;
        }
    } catch (error) {
        console.error('Erro:', error);
        showToast('Erro ao salvar mapeamento', 'error');
    }
}

async function deletarMapeamentoDescricao(descricaoOriginal, row, cell) {
    try {
        const response = await fetch('/api/mapeamento-descricao', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                descricao_original: descricaoOriginal
            })
        });

        const result = await response.json();

        if (result.success) {
            // Atualizar a row com os dados originais
            row.dataset.descricao = descricaoOriginal;
            row.dataset.temMapeamento = 'false';

            // Atualizar a célula
            cell.innerHTML = `${descricaoOriginal}<span class="edit-icon desc-edit-icon" title="Editar descrição">✎</span>`;

            showToast('Mapeamento removido. Descrição original restaurada.');
        } else {
            showToast('Erro ao remover mapeamento', 'error');
        }
    } catch (error) {
        console.error('Erro:', error);
        showToast('Erro ao remover mapeamento', 'error');
    }
}

function initTableSorting(table) {
    const headers = table.querySelectorAll('th[data-sort]');
    const allHeaders = table.querySelectorAll('th');
    const tbody = table.querySelector('tbody');

    headers.forEach((header) => {
        // Encontrar o índice real da coluna na tabela
        const colIndex = Array.from(allHeaders).indexOf(header);

        header.addEventListener('click', () => {
            const type = header.dataset.sort;
            const rows = Array.from(tbody.querySelectorAll('tr'));
            const isAsc = header.classList.contains('asc');

            // Resetar outros headers
            headers.forEach(h => {
                h.classList.remove('asc', 'desc');
                const icon = h.querySelector('.sort-icon');
                if(icon) icon.textContent = '↕';
            });

            // Alternar atual
            header.classList.toggle('asc', !isAsc);
            header.classList.toggle('desc', isAsc);

            const icon = header.querySelector('.sort-icon');
            if(icon) icon.textContent = !isAsc ? '▲' : '▼';

            rows.sort((a, b) => {
                let valA, valB;
                const cellA = a.children[colIndex];
                const cellB = b.children[colIndex];

                if (!cellA || !cellB) return 0;

                if (type === 'number') {
                    valA = parseFloat(cellA.dataset.val || cellA.textContent.replace(/[^\d.-]/g, '') || 0);
                    valB = parseFloat(cellB.dataset.val || cellB.textContent.replace(/[^\d.-]/g, '') || 0);
                } else {
                    valA = cellA.textContent.trim().toLowerCase();
                    valB = cellB.textContent.trim().toLowerCase();
                }

                if (valA < valB) return !isAsc ? -1 : 1;
                if (valA > valB) return !isAsc ? 1 : -1;
                return 0;
            });

            rows.forEach(row => tbody.appendChild(row));
        });
    });
}

// ============================================================================
// DRAG TRANSAÇÕES PARA RECORRENTES
// ============================================================================

function initTransactionDrag(container) {
    const draggableRows = container.querySelectorAll('.tx-draggable');

    draggableRows.forEach(row => {
        row.addEventListener('dragstart', handleTxDragStart);
        row.addEventListener('dragend', handleTxDragEnd);
    });
}

function handleTxDragStart(e) {
    const data = {
        descricao: this.dataset.descricao,
        categoria: this.dataset.categoria,
        valor: parseFloat(this.dataset.valor) || 0
    };

    e.dataTransfer.setData('application/json', JSON.stringify(data));
    e.dataTransfer.effectAllowed = 'move';

    this.classList.add('tx-dragging');

    // Highlight drop zones
    setTimeout(() => {
        const recorrentesCard = document.querySelector('.recorrentes-card');
        if (recorrentesCard) {
            recorrentesCard.classList.add('drop-zone-active');
        }

        // Destacar categorias como drop zones
        document.querySelectorAll('.category-row').forEach(row => {
            row.classList.add('category-drop-zone-active');
        });

        // Destacar subcategorias como drop zones (grupo inteiro)
        document.querySelectorAll('.subcategoria-group').forEach(group => {
            group.classList.add('subcategoria-drop-zone-active');
        });
    }, 0);
}

function handleTxDragEnd(e) {
    this.classList.remove('tx-dragging');

    // Remove drop zone highlight
    const recorrentesCard = document.querySelector('.recorrentes-card');
    if (recorrentesCard) {
        recorrentesCard.classList.remove('drop-zone-active', 'drop-zone-hover');
    }

    // Remover destaque das categorias e subcategorias
    document.querySelectorAll('.category-row').forEach(row => {
        row.classList.remove('category-drop-zone-active', 'category-drop-hover');
    });
    document.querySelectorAll('.subcategoria-group').forEach(group => {
        group.classList.remove('subcategoria-drop-zone-active', 'subcategoria-drop-hover');
    });
}

// Inicializar drop zone nos recorrentes
function initRecorrentesDropZone() {
    const recorrentesCard = document.querySelector('.recorrentes-card');
    if (!recorrentesCard) return;

    recorrentesCard.addEventListener('dragover', function(e) {
        e.preventDefault();
        e.dataTransfer.dropEffect = 'copy';
        this.classList.add('drop-zone-hover');
    });

    recorrentesCard.addEventListener('dragleave', function(e) {
        // Verificar se realmente saiu do card
        if (!this.contains(e.relatedTarget)) {
            this.classList.remove('drop-zone-hover');
        }
    });

    recorrentesCard.addEventListener('drop', async function(e) {
        e.preventDefault();
        this.classList.remove('drop-zone-active', 'drop-zone-hover');

        try {
            const jsonData = e.dataTransfer.getData('application/json');
            if (!jsonData) return;

            const data = JSON.parse(jsonData);

            // Abrir modal pré-preenchido ou adicionar diretamente
            if (typeof abrirModalRecorrentePreenchido === 'function') {
                abrirModalRecorrentePreenchido(data);
            } else if (typeof window.adicionarRecorrenteDireto === 'function') {
                await window.adicionarRecorrenteDireto(data);
            } else {
                // Fallback: adicionar diretamente via API
                const response = await fetch('/api/recorrentes/adicionar', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        descricao: data.descricao,
                        categoria: data.categoria,
                        valor: Math.abs(data.valor),
                        tipo: 'mensal'
                    })
                });
                const result = await response.json();

                if (result.success) {
                    showToast(`"${data.descricao}" adicionado aos recorrentes!`);
                    // Recarregar lista de recorrentes
                    if (typeof loadRecorrentes === 'function') {
                        loadRecorrentes();
                    }
                } else {
                    showToast(result.error || 'Erro ao adicionar recorrente', 'error');
                }
            }
        } catch (error) {
            console.error('Erro ao processar drop:', error);
            showToast('Erro ao adicionar recorrente', 'error');
        }
    });
}

// Inicializar quando DOM estiver pronto
document.addEventListener('DOMContentLoaded', function() {
    initRecorrentesDropZone();
    initCategoryDropZones();
});

// ============================================================================
// DRAG AND DROP PARA CATEGORIZAÇÃO
// ============================================================================

function initCategoryDropZones() {
    // Observar mudanças no DOM para adicionar drop zones a novas linhas de categoria
    const observer = new MutationObserver(() => {
        setupCategoryDropZones();
    });

    observer.observe(document.body, { childList: true, subtree: true });

    // Configurar drop zones iniciais
    setupCategoryDropZones();
}

function setupCategoryDropZones() {
    // Linhas de categoria no dashboard
    const categoryRows = document.querySelectorAll('.category-row:not([data-drop-initialized])');

    categoryRows.forEach(row => {
        row.setAttribute('data-drop-initialized', 'true');

        row.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            this.classList.add('category-drop-hover');
        });

        row.addEventListener('dragleave', function(e) {
            if (!this.contains(e.relatedTarget)) {
                this.classList.remove('category-drop-hover');
            }
        });

        row.addEventListener('drop', async function(e) {
            e.preventDefault();
            this.classList.remove('category-drop-hover');
            this.classList.remove('category-drop-zone-active');

            try {
                const jsonData = e.dataTransfer.getData('application/json');
                console.log('Drop data:', jsonData);
                if (!jsonData) {
                    console.log('No JSON data in drop');
                    return;
                }

                const data = JSON.parse(jsonData);
                const novaCategoria = this.dataset.categoria;

                console.log('Movendo transação:', data.descricao, 'para categoria:', novaCategoria);

                // Verificar se a categoria é diferente (permitir categoria vazia = Não Classificado)
                if (novaCategoria === data.categoria) {
                    console.log('Mesma categoria, ignorando');
                    return;
                }

                // Usar API de atualização por descrição
                const response = await fetch('/api/transacoes/atualizar-por-descricao', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        descricao: data.descricao,
                        categoria: novaCategoria || 'Não Classificado',
                        subcategoria: null
                    })
                });

                const result = await response.json();

                if (result.success) {
                    const qtd = result.transacoes_atualizadas || 1;
                    showToast(`Movido para "${novaCategoria || 'Não Classificado'}" (${qtd} transação${qtd > 1 ? 's' : ''})`);

                    // Mover visualmente (categoria, sem subcategoria)
                    moverTransacoesVisuais(data.descricao, novaCategoria || 'Não Classificado', null);
                } else {
                    showToast(result.error || 'Erro ao mover transação', 'error');
                }
            } catch (error) {
                console.error('Erro ao processar drop:', error);
                showToast('Erro ao mover transação', 'error');
            }
        });
    });

    // Grupos de subcategoria inteiros são drop zones (header + tabela)
    const subcatGroups = document.querySelectorAll('.subcategoria-group:not([data-drop-initialized])');

    subcatGroups.forEach(group => {
        group.setAttribute('data-drop-initialized', 'true');

        const header = group.querySelector('.subcategoria-header');
        if (!header) return;

        group.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.stopPropagation();
            e.dataTransfer.dropEffect = 'move';
            this.classList.add('subcategoria-drop-hover');
        });

        group.addEventListener('dragleave', function(e) {
            if (!this.contains(e.relatedTarget)) {
                this.classList.remove('subcategoria-drop-hover');
            }
        });

        group.addEventListener('drop', async function(e) {
            e.preventDefault();
            e.stopPropagation(); // Evitar propagação para categoria pai
            this.classList.remove('subcategoria-drop-hover');

            try {
                const jsonData = e.dataTransfer.getData('application/json');
                console.log('Drop subcategoria data:', jsonData);
                if (!jsonData) return;

                const data = JSON.parse(jsonData);

                // Pegar categoria e subcategoria do header
                const novaCategoria = header.dataset.categoria;
                const novaSubcategoria = header.dataset.subcategoria;

                console.log('Movendo para:', novaCategoria, '/', novaSubcategoria);

                if (!novaSubcategoria) return;

                // Usar a categoria do header de subcategoria (categoria pai)
                const response = await fetch('/api/transacoes/atualizar-por-descricao', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        descricao: data.descricao,
                        categoria: novaCategoria,
                        subcategoria: novaSubcategoria
                    })
                });

                const result = await response.json();

                if (result.success) {
                    const qtd = result.transacoes_atualizadas || 1;
                    showToast(`Movido para "${novaCategoria} → ${novaSubcategoria}" (${qtd} transação${qtd > 1 ? 's' : ''})`);

                    // Mover visualmente para o destino
                    moverTransacoesVisuais(data.descricao, novaCategoria, novaSubcategoria);
                } else {
                    showToast(result.error || 'Erro ao mover transação', 'error');
                }
            } catch (error) {
                console.error('Erro ao processar drop:', error);
                showToast('Erro ao mover transação', 'error');
            }
        });
    });
}

// ============================================================================
// ATUALIZAÇÃO VISUAL SEM RELOAD
// ============================================================================

function moverTransacoesVisuais(descricao, novaCategoria, novaSubcategoria) {
    // Encontrar todas as linhas com essa descrição
    const escapedDescricao = descricao.replace(/"/g, '\\"');
    const linhas = document.querySelectorAll(`tr[data-descricao="${escapedDescricao}"]`);

    // Encontrar o tbody de destino (se categoria/subcategoria estiver expandida)
    let tbodyDestino = null;
    let subcatGroupDestino = null;

    if (novaSubcategoria) {
        // Procurar grupo da subcategoria de destino
        const headers = document.querySelectorAll(`.subcategoria-header[data-subcategoria="${novaSubcategoria}"]`);
        headers.forEach(header => {
            if (header.dataset.categoria === novaCategoria) {
                subcatGroupDestino = header.closest('.subcategoria-group');
                tbodyDestino = subcatGroupDestino?.querySelector('.subcategoria-content tbody');
            }
        });
    }

    linhas.forEach(linha => {
        const subcatGroupOrigem = linha.closest('.subcategoria-group');
        const subcatContentOrigem = linha.closest('.subcategoria-content');

        // Clonar a linha antes de remover (para adicionar no destino)
        const linhaClone = linha.cloneNode(true);

        // Atualizar dados da linha clonada
        linhaClone.dataset.categoria = novaCategoria;
        linhaClone.dataset.subcategoria = novaSubcategoria || '';

        // Animar saída
        linha.style.transition = 'all 0.3s ease';
        linha.style.opacity = '0';
        linha.style.transform = 'translateX(-20px)';

        setTimeout(() => {
            linha.remove();

            // Atualizar contadores da origem
            if (subcatGroupOrigem) {
                atualizarContadoresSubcategoria(subcatGroupOrigem, subcatContentOrigem);
            }

            // Adicionar no destino (se estiver visível/expandido)
            if (tbodyDestino) {
                // Preparar animação de entrada
                linhaClone.style.opacity = '0';
                linhaClone.style.transform = 'translateX(20px)';
                tbodyDestino.appendChild(linhaClone);

                // Reinicializar eventos de drag na nova linha
                linhaClone.setAttribute('draggable', 'true');
                initRowDrag(linhaClone);

                // Animar entrada
                setTimeout(() => {
                    linhaClone.style.transition = 'all 0.3s ease';
                    linhaClone.style.opacity = '1';
                    linhaClone.style.transform = 'translateX(0)';
                }, 50);

                // Atualizar contadores do destino
                atualizarContadoresSubcategoria(subcatGroupDestino, tbodyDestino.closest('.subcategoria-content'));
            }
        }, 300);
    });
}

function atualizarContadoresSubcategoria(subcatGroup, subcatContent) {
    if (!subcatGroup) return;

    const tbody = subcatContent?.querySelector('tbody');
    const linhasRestantes = tbody?.querySelectorAll('tr').length || 0;

    // Atualizar contador de itens
    const qtdSpan = subcatGroup.querySelector('.subcategoria-qtd');
    if (qtdSpan) {
        qtdSpan.textContent = `${linhasRestantes} item${linhasRestantes !== 1 ? 's' : ''}`;
    }

    // Atualizar total da subcategoria
    const totalSpan = subcatGroup.querySelector('.subcategoria-total');
    if (totalSpan && tbody) {
        let novoTotal = 0;
        tbody.querySelectorAll('tr').forEach(tr => {
            novoTotal += parseFloat(tr.dataset.valor) || 0;
        });
        totalSpan.textContent = formatarMoeda(novoTotal);
    }

    // Remover grupo se vazio
    if (linhasRestantes === 0) {
        subcatGroup.style.transition = 'all 0.3s ease';
        subcatGroup.style.opacity = '0';
        setTimeout(() => subcatGroup.remove(), 300);
    }
}

function initRowDrag(row) {
    row.addEventListener('dragstart', function(e) {
        const descricao = this.dataset.descricao;
        const categoria = this.dataset.categoria;
        const valor = this.dataset.valor;

        const dragData = { descricao, categoria, valor };
        e.dataTransfer.setData('application/json', JSON.stringify(dragData));
        e.dataTransfer.effectAllowed = 'move';

        this.classList.add('dragging');

        setTimeout(() => {
            document.querySelectorAll('.category-row').forEach(row => {
                row.classList.add('category-drop-zone-active');
            });
            document.querySelectorAll('.subcategoria-group').forEach(group => {
                group.classList.add('subcategoria-drop-zone-active');
            });
        }, 0);
    });

    row.addEventListener('dragend', function() {
        this.classList.remove('dragging');
        document.querySelectorAll('.category-row').forEach(row => {
            row.classList.remove('category-drop-zone-active', 'category-drop-hover');
        });
        document.querySelectorAll('.subcategoria-group').forEach(group => {
            group.classList.remove('subcategoria-drop-zone-active', 'subcategoria-drop-hover');
        });
    });
}

// Função simplificada para remover (usada quando não há destino visível)
function removerTransacoesVisuais(descricao) {
    moverTransacoesVisuais(descricao, null, null);
}

// ============================================================================
// UTILITÁRIOS
// ============================================================================

const Utils = {
    moeda: formatarMoeda,
    data: formatarData
};

// Exportar para uso global
window.Utils = Utils;
window.initTableSorting = initTableSorting;
window.initTransactionDrag = initTransactionDrag;
