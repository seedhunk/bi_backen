"""
IMPORTANT: All unit for size is cm
"""


class SingleAbsFitValue2FitValueRule:
    absFitValueName: str  # from  # 这个fit value是基于什么值计算的
    fitValueName: str  # to  # 这个fit value的列名是什么
    easeValueName: str  # decide range  # 根据这个ease值的范围决定权重
    rangeNode: list[float]  # the node of range  # 范围的节点值 从大到小
    rangeWeight: list[float]  # when range decided, what its weight 确定absFitValue取值范围后决定使用哪个权重，所以比Node len+1

    def __init__(self, absFitValueName: str, fitValueName: str, easeValueName: str, rangeNode: list[float],
                 rangeWeight: list[float]):
        if len(rangeNode) != 0 and len(rangeNode) != len(rangeWeight) - 1:
            raise Exception(f"len(rangeNode) != len(rangeWeight)-1 from '{absFitValueName}' to '{fitValueName}'")
        self.absFitValueName = absFitValueName
        self.fitValueName = fitValueName
        self.easeValueName = easeValueName
        self.rangeNode = rangeNode
        self.rangeWeight = rangeWeight

    def __str__(self):
        return ("{"
                f'absFitValueName:"{self.absFitValueName}",'
                f'fitValueName:"{self.fitValueName}",'
                f'easeValueName:"{self.easeValueName}",'
                f'rangeNode:{self.rangeNode},'
                f'rangeWeight:{self.rangeWeight}'
                "}")

    def get_weight(self, ease: float) -> float:
        i = 0
        for node in self.rangeNode:
            if ease > node:
                break
            i = i + 1
        return self.rangeWeight[i]


class ScreenRule:
    idealEase: dict[str, float]  # minus this from ease to absFitValue

    absFitValue2FitValueRule: list[SingleAbsFitValue2FitValueRule]  # param used to get fitValue from absFitValue

    allWeighting: dict[str, float]  # weight from absFitValue to overall

    easeThreshold: dict[str, float]  # filter result which is too small at some bodyPart

    def __init__(self, originRuleIdealEase: dict[str, float], originRuleAbsFitValue2FitValue: list[dict],
                 originRuleAllWeighting: dict[str, float], originRuleEaseThreshold: dict[str, float]):
        self.idealEase = originRuleIdealEase
        absFitValue2FitValueRule = []
        for params in originRuleAbsFitValue2FitValue:
            absFitValue2FitValueRule.append(SingleAbsFitValue2FitValueRule(**params))
        self.absFitValue2FitValueRule = absFitValue2FitValueRule
        self.allWeighting = originRuleAllWeighting
        self.easeThreshold = originRuleEaseThreshold

    def __str__(self):
        return (f'{{'
                f'"idealEase":{self.idealEase},'
                f'"absFitValue2FitValueRule":{self.absFitValue2FitValueRule},'
                f'"allWeighting":{self.allWeighting},'
                f'"easeThreshold":{self.easeThreshold}'
                f'}}')

    def not_too_small_for_recommendation(self, easeDataOfOneSize: dict[str, float]) -> bool:
        for (bodyPart, threshold) in self.easeThreshold.items():
            if bodyPart in easeDataOfOneSize:
                if easeDataOfOneSize[bodyPart] < threshold:
                    return False
        return True


class Recommendation:
    bodyData: dict[str, float]
    sizeChart: dict[str, dict[str, float]]  # {"S": {"Bust": 99.1} }
    screenRule: ScreenRule

    easeData: dict[str, dict[str, float]]  # {"S": {"Bust": -0.8} }
    absFitValue: dict[str, dict[str, float]]  # {"S": {"Bust": 6.8} }
    fitValue: dict[str, dict[str, float]]  # {"S": {"Bust": 12.3} }
    overall: dict[str, float]  # {"S": 26.7, "M":21.9}
    overallOder: list[dict]  # overall after ordering
    # [
    #   {
    #     "sizeName": "M",
    #     "overallValue": ...,
    #     "mostMisfitBodyPartName": ...,
    #     "mostMisfitAbsFitValue": ...,
    #     "mostMisfitBodyPartEaseValue": ...
    #   },
    #   ...
    #  ]

    overallOderAfterFilter: list[dict]  # filter according easeThreshold
    recommendResult: list[dict]

    def __init__(self,
                 bodyData: dict[str, float],  # {"Bust": 98,...}
                 sizeChart: dict[str, dict[str, float]],  # {"S": {"Bust": 99.1}, ...}
                 # screen rule params:
                 idealEase: dict[str, float],  # {"Bust": 6.0, ...}
                 absFitValue2FitValue: list[dict],
                 # [
                 #   {
                 #     "absFitValueName":"shoulder" ,
                 #     "fitValueName": "ShoulderByBust",
                 #     "easeValueName": "Bust",
                 #     "rangeNode":   [17, 8, 4, -1 ],
                 #     "rangeWeight": [2 , 2, 1, 1.7, 3]
                 #   },
                 #   ...
                 # ]
                 allWeighting: dict[str, float],  # {"Bust": 1, "shoulderByBust":1, ...}
                 easeThreshold: dict[str, float]  # {"Bust":-1, "Waist":-1, ...}
                 ):
        if len(absFitValue2FitValue) != len(allWeighting):
            raise Exception(
                "len of fitValue is not the same as allWeighting, 也就是说计算allover时会有fitValue无权重信息")
        self.bodyData = bodyData
        self.sizeChart = sizeChart
        self.screenRule = ScreenRule(idealEase, absFitValue2FitValue, allWeighting, easeThreshold)
        self.easeData = {}
        self.absFitValue = {}
        self.fitValue = {}
        self.overall = {}
        self.overallOder = []
        self.rangeNode = {}
        self.absFitValue2FitValue = absFitValue2FitValue

        self.overallOderAfterFilter = []
        self.recommendResult = []

        self.__process__()

    def __process__(self):
        # Node
        for item in self.absFitValue2FitValue:
            self.rangeNode[item["fitValueName"]]= item["rangeNode"]
        # Ease
        for (sizeName, sizeChart4OneSizeName) in self.sizeChart.items():
            easeDataItem = {}
            for (bodyPart, size) in sizeChart4OneSizeName.items():
                if bodyPart in self.bodyData:
                    easeDataItem[bodyPart] = size - self.bodyData[bodyPart]
            self.easeData[sizeName] = easeDataItem

        # ABS Fit value
        for (sizeName, easeDataItem) in self.easeData.items():
            absFitValueItem = {}
            for (bodyPart, ease) in easeDataItem.items():
                absFitValueItem[bodyPart] = abs(ease - self.screenRule.idealEase[bodyPart])
            self.absFitValue[sizeName] = absFitValueItem
        # Fit value
        for (sizeName, absFitValueItem) in self.absFitValue.items():
            fitValueItem = {}
            for x in self.screenRule.absFitValue2FitValueRule:
                if x.easeValueName in self.easeData[sizeName] and x.easeValueName in absFitValueItem:
                    ease = self.easeData[sizeName][x.easeValueName]
                    absFitValue = absFitValueItem[x.absFitValueName]
                    fitValueItem[x.fitValueName] = absFitValue * x.get_weight(ease)
            self.fitValue[sizeName] = fitValueItem
        # overall
        for (sizeName, fitValueItem) in self.fitValue.items():
            overallItem = 0
            for (key, fitValue) in fitValueItem.items():
                overallItem += fitValue * self.screenRule.allWeighting[key]
            self.overall[sizeName] = overallItem
        # order and filter
        """
        NOTE: 
            order -> filter 
            saving processing data through this way.
        """
        overallNotOrder = []
        for (sizeName, overallValue) in self.overall.items():
            mostMisfitBodyPartName = max(self.absFitValue[sizeName])
            x = {
                "sizeName": sizeName,
                "overallValue": overallValue,
                "mostMisfitBodyPartName": mostMisfitBodyPartName,
                "mostMisfitAbsFitValue": self.absFitValue[sizeName][mostMisfitBodyPartName],
                "mostMisfitBodyPartEaseValue": self.easeData[sizeName][mostMisfitBodyPartName]
            }
            overallNotOrder.append(x)
        self.overallOder = sorted(overallNotOrder, key=lambda item: item["overallValue"])

        self.overallOderAfterFilter = [x for x in self.overallOder if
                                       self.screenRule.not_too_small_for_recommendation(self.easeData[x["sizeName"]])]

        # recommendation
        self.recommendResult = self.overallOderAfterFilter[0:3]

    def __str__(self):
        return (f'{{'
                f'"bodyData": {self.bodyData},'
                f'"sizeChart": {self.sizeChart},'
                f'"screenRule": {self.screenRule},'
                f'"easeData": {self.easeData},'
                f'"absFitValue": {self.absFitValue},'
                f'"fitValue": {self.fitValue},'
                f'"overall": {self.overall},'
                f'"overallOder": {self.overallOder},'
                f'"overallOderAfterFilter": {self.overallOderAfterFilter},'
                f'"recommendResult":{self.recommendResult}'
                f'"rangeNode":{self.rangeNode}'
                f'}}')

# Example:
# print(Recommendation(
#     {"Bust": 99.5, "Waist": 89.9, "Shoulder": 45.0, "Height": 167.0},
#     {
#         "S": {"Bust": 98.7, "Waist": 87.4, "Shoulder": 43.3, "Height": 167.0},
#         "M": {"Bust": 106, "Waist": 92.5, "Shoulder": 44.5, "Height": 176.3},
#         "HS": {"Bust": 106.7, "Waist": 93.2, "Shoulder": 46.9, "Height": 186.0},
#         "L2-out": {"Bust": 109.5, "Waist": 100.7, "Shoulder": 47.3, "Height": 179.0},
#         "L": {"Bust": 109.7, "Waist": 96.2, "Shoulder": 46.3, "Height": 178.0},
#         "HM": {"Bust": 110.9, "Waist": 97.4, "Shoulder": 48.3, "Height": 186.0},
#         "L2": {"Bust": 113.4, "Waist": 102.1, "Shoulder": 49.8, "Height": 174.6},
#         "HL": {"Bust": 114.2, "Waist": 100.6, "Shoulder": 49.4, "Height": 185.0},
#         "L3": {"Bust": 122.7, "Waist": 107.9, "Shoulder": 52.0, "Height": 177.0}
#     },
#     {"Bust": 6, "Waist": 6, "Shoulder": 0, "Height": 0.0},
#     [
#         {
#             "absFitValueName": "Bust",
#             "fitValueName": "Bust",
#             "easeValueName": "Bust",
#             "rangeNode": [17, 8, 4, -1],
#             "rangeWeight": [2.5, 2, 1, 1.8, 3]
#         }, {
#             "absFitValueName": "Waist",
#             "fitValueName": "Waist",
#             "easeValueName": "Waist",
#             "rangeNode": [17, 8, 4, -1],
#             "rangeWeight": [3, 1, 0.8, 1.5, 3]
#         }, {
#             "absFitValueName": "Shoulder",
#             "fitValueName": "ShoulderByBust",
#             "easeValueName": "Bust",
#             "rangeNode": [17, 8, 4, -1],
#             "rangeWeight": [2, 2, 1, 1.7, 3]
#         }, {
#             "absFitValueName": "Shoulder",
#             "fitValueName": "Shoulder",
#             "easeValueName": "Shoulder",
#             "rangeNode": [],
#             "rangeWeight": [0]
#         }, {
#             "absFitValueName": "Shoulder",
#             "fitValueName": "ShoulderMinus",
#             "easeValueName": "Shoulder",
#             "rangeNode": [10, 5],
#             "rangeWeight": [0, 0.8, 1.41]
#         }, {
#             "absFitValueName": "Height",
#             "fitValueName": "Height",
#             "easeValueName": "Height",
#             "rangeNode": [10, 5, 0, -5, -12],
#             "rangeWeight": [2, 2.03, 1, 1.8, 1.8, 3]
#         }
#     ],
#     {"Bust": 1.0, "ShoulderByBust": 1, "Waist": 0.55, "Shoulder": 0, "ShoulderMinus": 0, "Height": 1},
#     {"Bust": -1, "Waist": -1}
# ))
