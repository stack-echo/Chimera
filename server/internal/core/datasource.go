package core

// DataSourceHandler 定义特定数据源（如飞书、钉钉）需要实现的逻辑接口
type DataSourceHandler interface {
	// ValidateConfig 校验前端传来的 Config JSON/Map 是否合法
	ValidateConfig(config map[string]interface{}) error
}

// DataSourceRegistry 数据源处理器注册表
type DataSourceRegistry struct {
	handlers map[string]DataSourceHandler
}

// 全局单例，方便 init() 注册
var GlobalRegistry = &DataSourceRegistry{
	handlers: make(map[string]DataSourceHandler),
}

func (r *DataSourceRegistry) Register(sourceType string, handler DataSourceHandler) {
	r.handlers[sourceType] = handler
}

func (r *DataSourceRegistry) Get(sourceType string) (DataSourceHandler, bool) {
	h, ok := r.handlers[sourceType]
	return h, ok
}

// Validate 辅助函数：如果注册了校验器则校验，没注册（如 file）则默认通过
func (r *DataSourceRegistry) Validate(sourceType string, config map[string]interface{}) error {
	if handler, ok := r.Get(sourceType); ok {
		return handler.ValidateConfig(config)
	}
	// 如果没有注册特定的 Handler (比如 file 类型暂不需要复杂校验)，默认放行
	// 或者你可以配置成 return errors.New("未知的数据源类型") 来强制要求注册
	return nil
}
