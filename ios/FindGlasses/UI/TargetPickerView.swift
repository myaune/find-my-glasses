import SwiftUI

/// 다른 물건 찾기 (부가 기능). 안경 외 대상은 테스트하지 않았다고 창에 적는다.
/// 모델은 그대로 두고 대상 클래스만 바꾼다. 앱을 켜면 항상 안경이다.
struct TargetPickerView: View {
    @EnvironmentObject var engine: FinderEngine
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(L("target_title"))
                .font(.system(size: 22))
                .padding(.top, 24)
            Text(L("target_note"))
                .font(.system(size: 14))
                .foregroundStyle(Color(white: 0.62))
                .padding(.top, 8)
                .padding(.bottom, 12)

            ForEach(ModelCatalog.Target.allCases, id: \.self) { t in
                Button {
                    engine.setTarget(t)
                    dismiss()
                } label: {
                    HStack {
                        Text("\(t.emoji)  \(L(t.labelKey))").font(.system(size: 19)).foregroundStyle(.white)
                        Spacer()
                        if t == engine.target { Image(systemName: "checkmark").foregroundStyle(.white) }
                    }
                    .frame(height: 52)
                }
            }
            Spacer()
        }
        .padding(.horizontal, 24)
        .presentationDetents([.medium])
    }
}
