import type { DOMWrapper } from '@vue/test-utils'

/**
 * 本地语义查询: 任务卡要求按 role / text 断言, 但 004 不新增第三方依赖,
 * 所以用与 testing-library 同名的小工具代替。查询不到或多于一个都直接失败。
 */
interface ElementQuery {
  findAll(selector: string): DOMWrapper<Element>[]
}

const ROLE_SELECTORS: Record<string, string> = {
  button: 'button',
  heading: 'h1, h2, h3, h4, h5, h6',
  list: 'ul, ol',
  listitem: 'li',
  link: 'a[href]',
  alert: '[role="alert"]',
  status: '[role="status"]',
}

function onlyMatch(matches: DOMWrapper<Element>[], query: string): DOMWrapper<Element> {
  const first = matches[0]
  if (first === undefined) {
    throw new Error(`未找到元素: ${query}`)
  }
  if (matches.length > 1) {
    throw new Error(`匹配到多个元素: ${query}`)
  }
  return first
}

function directText(element: Element): string {
  return Array.from(element.childNodes)
    .filter((node) => node.nodeType === Node.TEXT_NODE)
    .map((node) => node.textContent ?? '')
    .join('')
    .trim()
}

export function getByText(wrapper: ElementQuery, text: string): DOMWrapper<Element> {
  // 只匹配自身文本节点, 避免 <li> 命中时父级 <ul> 也命中
  const matches = wrapper.findAll('*').filter((node) => directText(node.element) === text)
  return onlyMatch(matches, `text="${text}"`)
}

export function getByRole(
  wrapper: ElementQuery,
  role: string,
  options: { name?: string } = {},
): DOMWrapper<Element> {
  const selector = ROLE_SELECTORS[role] ?? `[role="${role}"]`
  const matches = wrapper.findAll(selector).filter((node) => {
    if (options.name === undefined) {
      return true
    }
    return node.text().includes(options.name)
  })
  return onlyMatch(matches, `role=${role} name="${options.name ?? '*'}"`)
}