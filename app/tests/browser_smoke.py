"""Teste funcional em Chromium real; Playwright só é necessário para este teste."""
from pathlib import Path
import sys
import tempfile
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server import App,LocalServer,Handler
from playwright.sync_api import sync_playwright,expect

def run():
    with tempfile.TemporaryDirectory() as directory:
        app=App(directory);server=LocalServer(('127.0.0.1',0),Handler);server.app=app
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
                page=browser.new_page();page.set_default_timeout(10000);errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                origin=f'http://127.0.0.1:{server.server_port}'
                page.goto(origin+'/#launch='+app.launch_token+'&setup='+app.bootstrap)
                page.get_by_label('Nome do administrador').fill('Responsável de teste')
                page.get_by_label('Usuário',exact=True).fill('admin')
                page.get_by_label('Senha',exact=True).fill('Senha-do-teste-2026!')
                page.get_by_label('Confirme a senha').fill('Senha-do-teste-2026!')
                page.get_by_role('button',name='Criar administrador').click()
                expect(page.get_by_role('heading',name='Dashboard',exact=True)).to_be_visible()
                page.get_by_role('button',name='Especificações',exact=True).click()
                expect(page.get_by_role('heading',name='Especificações',exact=True)).to_be_visible()
                rows=page.locator('tbody tr')
                # Painel representativo: umidade, com limites definidos.
                for i in range(rows.count()):
                    row=rows.nth(i);row.locator('input[type=checkbox]').set_checked(row.locator('td').first.inner_text()=='Umidade')
                page.get_by_role('button',name='Salvar especificações').click()
                expect(page.get_by_role('alert')).to_contain_text('Configuração salva')
                page.get_by_role('button',name='Nova amostra',exact=True).click()
                page.get_by_label('Número da amostra').fill('AM-001')
                page.get_by_label('Número do tambor').fill('T-001')
                payload='<img src=x onerror="window.INJECTED=1">'
                page.get_by_label('Código do produtor').fill(payload)
                page.get_by_label('Umidade (%)').fill('18,5')
                page.get_by_role('button',name='Registrar análise').click()
                expect(page.get_by_role('alert')).to_contain_text('APROVADA')
                expect(page.locator('tbody')).to_contain_text(payload)
                assert page.evaluate('window.INJECTED') is None
                assert page.locator('tbody img').count()==0
                with page.expect_download() as info:page.get_by_role('button',name='Exportar Excel (CSV)').click()
                downloaded=Path(info.value.path()).read_text(encoding='utf-8-sig')
                assert 'LAU00001' in downloaded
                assert page.evaluate('safeCsv("=1+1")').startswith('"\'')
                assert page.evaluate('safeCsv("\\t=1+1")').startswith('"\'')
                page.on('dialog',lambda d:d.accept())
                page.get_by_role('button',name='Liberar',exact=True).click()
                expect(page.get_by_role('alert')).to_contain_text('Análise liberada')
                assert page.get_by_role('button',name='Editar',exact=True).count()==0
                page.evaluate('window.print=()=>{window.PRINTED=true;}')
                page.get_by_role('button',name='Laudo',exact=True).click()
                expect(page.locator('#print-area')).to_contain_text('LAU00001')
                expect(page.locator('#print-area')).to_contain_text('Responsável de teste')
                assert page.evaluate('window.INJECTED') is None
                assert page.locator('#print-area .report-warning').count()==0
                page.get_by_role('button',name='Etiqueta',exact=True).click()
                expect(page.locator('#print-area .label-print')).to_have_count(1)
                page.get_by_role('button',name='Rastreabilidade',exact=True).click()
                page.get_by_role('searchbox').fill('LAU00001');page.get_by_role('button',name='Consultar',exact=True).click()
                expect(page.get_by_role('heading',name='LAU00001')).to_be_visible()
                page.get_by_role('button',name='Usuários',exact=True).click()
                page.get_by_label('Nome',exact=True).fill('Operador')
                page.get_by_label('Login',exact=True).fill('operador')
                page.get_by_label('Senha inicial').fill('Senha-operador-2026!')
                page.get_by_label('Perfil').select_option('ASSISTENTE')
                page.get_by_role('button',name='Criar usuário',exact=True).click()
                expect(page.get_by_role('alert')).to_contain_text('Usuário criado')
                page.get_by_role('button',name='Backup e auditoria',exact=True).click()
                page.get_by_role('button',name='Verificar integridade').click();expect(page.get_by_role('alert')).to_contain_text('Integridade SQLite')
                page.get_by_role('button',name='Criar backup completo').click();expect(page.get_by_role('alert')).to_contain_text('Cópia verificada')
                page.get_by_role('button',name='Sair',exact=True).click()
                page.get_by_label('Usuário',exact=True).fill('operador')
                page.get_by_label('Senha',exact=True).fill('Senha-operador-2026!')
                page.get_by_role('button',name='Entrar',exact=True).click()
                expect(page.get_by_role('heading',name='Dashboard',exact=True)).to_be_visible()
                assert page.get_by_role('button',name='Usuários',exact=True).count()==0
                assert page.get_by_role('button',name='Backup e auditoria',exact=True).count()==0
                page.get_by_role('button',name='Amostras',exact=True).click()
                assert page.get_by_role('button',name='Liberar',exact=True).count()==0
                assert page.get_by_role('button',name='Laudo',exact=True).count()==0
                page.get_by_role('button',name='Sair',exact=True).click()
                page.get_by_label('Usuário',exact=True).fill('admin')
                page.get_by_label('Senha',exact=True).fill('Senha-do-teste-2026!')
                page.get_by_role('button',name='Entrar',exact=True).click()
                page.get_by_role('button',name='Backup e auditoria',exact=True).click()
                page.get_by_role('button',name='Encerrar aplicativo',exact=True).click()
                expect(page.get_by_role('heading',name='Aplicativo encerrado')).to_be_visible()
                thread.join(timeout=2);assert not thread.is_alive()
                assert not errors,errors
                page.screenshot(path=str(Path(__file__).resolve().parents[1]/'interface-validada.png'),full_page=True)
                browser.close()
                print('PASSOU: cadastro inicial, login, configuração, amostra, liberação, laudo, etiqueta, rastreabilidade, usuário, integridade, backup, logout e ACL na interface. Encerramento autenticado validado. Sem erros JS; tentativa XSS inerte.')
        finally:server.shutdown();server.server_close()

if __name__=='__main__':run()
