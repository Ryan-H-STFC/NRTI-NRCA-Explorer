from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QMenu, QAction
from PyQt5.QtGui import QIcon


class FigureCanvas(FigureCanvasQTAgg):
    def __init__(self, figure: Figure = None, widgetParent=None):
        super(FigureCanvasQTAgg, self).__init__(figure)
        self.widgetParent = widgetParent

    def contextMenuEvent(self, event):

        menu = QMenu()

        actionDelete = menu.addMenu(QIcon(".\\src\\img\\delete-component.svg"), 'Remove Graph')
        try:
            axis = self.figure.get_axes()[0]
            graphs = list(zip(axis.get_lines(), axis.get_legend().get_lines()))
            graphDict = {graph[1].get_label(): graph for graph in graphs}
            actionDelete.addActions([QAction(name, actionDelete) for name in graphDict.keys()])
        except IndexError:
            return

        res = menu.exec_(event.globalPos())
        if res is not None:
            graphLine = graphDict[res.text()][0]
            graphLine.remove()

            # graphDict[res.text()][1].remove()
            self.widgetParent.plottedSubstances.remove((graphDict[res.text()][0].get_gid(), 'ToF' in res.text()))

            for anno in self.widgetParent.elementData[res.text()].annotations:
                anno.remove()
            self.widgetParent.elementDataNames.clear()
            self.widgetParent.elementData.pop(res.text())
            for row in self.widgetParent.titleRows:
                self.widgetParent.table.setItemDelegateForRow(row, None)
            self.widgetParent.updateLegend()
            self.widgetParent.addTableData()
