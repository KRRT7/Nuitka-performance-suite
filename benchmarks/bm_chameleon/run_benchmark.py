import functools

# import pyperf

from chameleon import PageTemplate
from time import perf_counter_ns


BIGTABLE_ZPT = """\
<table xmlns="http://www.w3.org/1999/xhtml"
xmlns:tal="http://xml.zope.org/namespaces/tal">
<tr tal:repeat="row python: options['table']">
<td tal:repeat="c python: row.values()">
<span tal:define="d python: c + 1"
tal:attributes="class python: 'column-' + str(d)"
tal:content="python: d" />
</td>
</tr>
</table>"""


# def main():
#     runner = pyperf.Runner()
#     runner.metadata["description"] = "Chameleon template"

#     tmpl = PageTemplate(BIGTABLE_ZPT)
#     table = [
#         dict(a=1, b=2, c=3, d=4, e=5, f=6, g=7, h=8, i=9, j=10) for x in range(500)
#     ]
#     options = {"table": table}


#     func = functools.partial(tmpl, options=options)
#     runner.bench_func("chameleon", func)
def main():
    tmpl = PageTemplate(BIGTABLE_ZPT)
    table = [
        dict(a=1, b=2, c=3, d=4, e=5, f=6, g=7, h=8, i=9, j=10) for x in range(5000) for y in range(5)
    ]
    options = {"table": table}
    func = functools.partial(tmpl, options=options)
    func()


if __name__ == "__main__":
    start = perf_counter_ns()
    main()
    end = perf_counter_ns()
    with open("bench_time.txt", "w") as f:
        f.write(str(end - start))